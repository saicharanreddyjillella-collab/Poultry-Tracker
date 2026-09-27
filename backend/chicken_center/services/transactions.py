"""
Chicken Center transaction service.

Each function records a domain row AND posts the matching money voucher
(accounting) and stock movement (inventory) inside one atomic transaction.
WhatsApp fires AFTER commit, best-effort — a failed message never rolls back
a saved sale.

The accounting core stays pure: this module coordinates the two cores.
"""
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from accounting.models import Account, Party
from accounting.services import post_voucher, reverse_voucher
from inventory.models import Item
from inventory.services import record_movement, reverse_movements_for_voucher
from ..models import Sale, Purchase, Collection, Payment, Expense, Shrinkage, BUSINESS
from . import whatsapp as wa


def D(v):
    return Decimal(str(v))


def _acc(code):
    return Account.objects.get(code=code)


# ─────────────────────────── SALE ───────────────────────────

def create_sale(*, party, item, date, weight_kg, rate_per_kg, note='', user=None):
    """Dr Customer / Cr Sales, reduce stock, then WhatsApp the customer."""
    weight_kg = D(weight_kg)
    rate = D(rate_per_kg)
    if weight_kg <= 0 or rate <= 0:
        raise ValidationError("Weight and rate must be positive.")
    amount = (weight_kg * rate).quantize(Decimal('0.01'))

    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='SALE',
            narration=f"Sale to {party.name}: {weight_kg}kg",
            business=BUSINESS, source_module='chicken_center.sale', user=user,
            lines=[
                {'account': _acc('DEBTORS'), 'party': party, 'debit': amount},
                {'account': item.sales_account or _acc('SALES'), 'credit': amount},
            ],
        )
        record_movement(item=item, mtype='SALE_OUT', qty=weight_kg,
                        unit=item.base_unit, date=date, business=BUSINESS,
                        voucher=v, source_module='chicken_center.sale')
        sale = Sale.objects.create(
            party=party, item=item, date=date, weight_kg=weight_kg,
            rate_per_kg=rate, amount=amount, note=note, voucher=v, created_by=user,
        )

    # after-commit messaging (best-effort)
    balance = party.balance()
    res = wa.send_whatsapp(party.phone, wa.build_sale_message(
        customer_name=party.name, weight_kg=weight_kg, amount=amount, balance=balance))
    Sale.objects.filter(id=sale.id).update(whatsapp_status=res['status'])
    sale.whatsapp_status = res['status']
    return sale


# ───────────────────────── PURCHASE ─────────────────────────

def create_purchase(*, party, item, date, weight_kg, rate_per_kg, note='', user=None):
    """Dr Purchases / Cr Supplier, increase stock."""
    weight_kg = D(weight_kg)
    rate = D(rate_per_kg)
    if weight_kg <= 0 or rate <= 0:
        raise ValidationError("Weight and rate must be positive.")
    amount = (weight_kg * rate).quantize(Decimal('0.01'))

    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='PURCHASE',
            narration=f"Purchase from {party.name}: {weight_kg}kg",
            business=BUSINESS, source_module='chicken_center.purchase', user=user,
            lines=[
                {'account': item.purchase_account or _acc('PURCHASES'), 'debit': amount},
                {'account': _acc('CREDITORS'), 'party': party, 'credit': amount},
            ],
        )
        record_movement(item=item, mtype='PURCHASE_IN', qty=weight_kg,
                        unit=item.base_unit, date=date, business=BUSINESS,
                        voucher=v, source_module='chicken_center.purchase')
        return Purchase.objects.create(
            party=party, item=item, date=date, weight_kg=weight_kg,
            rate_per_kg=rate, amount=amount, note=note, voucher=v, created_by=user,
        )


# ──────────────────────── COLLECTION ────────────────────────

_MODE_ACCOUNT = {'CASH': 'CASH', 'UPI': 'UPI', 'BANK': 'BANK'}


def create_collection(*, party, date, amount, mode='CASH', note='', user=None):
    """Dr Cash/UPI/Bank / Cr Customer, allocate oldest-first to pending
    bills, hold any excess as advance, then WhatsApp receipt."""
    from ..models import Sale, Allocation
    amount = D(amount)
    if amount <= 0:
        raise ValidationError("Amount must be positive.")

    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='RECEIPT',
            narration=f"Received from {party.name} ({mode})",
            business=BUSINESS, source_module='chicken_center.collection', user=user,
            lines=[
                {'account': _acc(_MODE_ACCOUNT[mode]), 'debit': amount},
                {'account': _acc('DEBTORS'), 'party': party, 'credit': amount},
            ],
        )
        coll = Collection.objects.create(
            party=party, date=date, amount=amount, mode=mode, note=note,
            voucher=v, created_by=user,
        )

        # Allocate oldest-first to this party's pending/partly bills.
        remaining = amount
        pending = (Sale.objects
                   .filter(party=party, status__in=['PENDING', 'PARTLY'])
                   .exclude(voucher__is_reversed=True)
                   .order_by('date', 'id')
                   .select_for_update())
        for bill in pending:
            if remaining <= 0:
                break
            due = bill.amount_due
            if due <= 0:
                continue
            applied = min(due, remaining)
            Allocation.objects.create(collection=coll, sale=bill, amount=applied)
            bill.amount_received += applied
            bill.recompute_status()
            bill.save(update_fields=['amount_received', 'status'])
            remaining -= applied

        # Anything left over is an advance (customer now in credit).
        if remaining > 0:
            coll.advance = remaining
            coll.save(update_fields=['advance'])

    balance = party.balance()
    res = wa.send_whatsapp(party.phone, wa.build_collection_message(
        customer_name=party.name, amount=amount, mode=mode, balance=balance))
    Collection.objects.filter(id=coll.id).update(whatsapp_status=res['status'])
    coll.whatsapp_status = res['status']
    return coll


# ───────────────────────── PAYMENT ──────────────────────────

def create_payment(*, party, date, amount, mode='CASH', note='', user=None):
    """Dr Supplier / Cr Cash/UPI/Bank."""
    amount = D(amount)
    if amount <= 0:
        raise ValidationError("Amount must be positive.")

    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='PAYMENT',
            narration=f"Paid {party.name} ({mode})",
            business=BUSINESS, source_module='chicken_center.payment', user=user,
            lines=[
                {'account': _acc('CREDITORS'), 'party': party, 'debit': amount},
                {'account': _acc(_MODE_ACCOUNT[mode]), 'credit': amount},
            ],
        )
        return Payment.objects.create(
            party=party, date=date, amount=amount, mode=mode, note=note,
            voucher=v, created_by=user,
        )


# ───────────────────────── EXPENSE ──────────────────────────

def create_expense(*, date, account_code, amount, mode='CASH', note='', user=None):
    """Dr <expense head> / Cr Cash/UPI/Bank. Auto-reduces month profit."""
    amount = D(amount)
    if amount <= 0:
        raise ValidationError("Amount must be positive.")
    exp_acc = _acc(account_code)
    if exp_acc.type != 'EXPENSE':
        raise ValidationError(f"{account_code} is not an expense account.")

    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='EXPENSE',
            narration=note or exp_acc.name,
            business=BUSINESS, source_module='chicken_center.expense', user=user,
            lines=[
                {'account': exp_acc, 'debit': amount},
                {'account': _acc(_MODE_ACCOUNT[mode]), 'credit': amount},
            ],
        )
        return Expense.objects.create(
            date=date, account_code=account_code, amount=amount, mode=mode,
            note=note, voucher=v, created_by=user,
        )


# ──────────────────────── SHRINKAGE ─────────────────────────

def create_shrinkage(*, item, date, weight_kg, value=0, reason='', user=None):
    """Reduce stock and book the loss: Dr Shrinkage / Cr Stock."""
    weight_kg = D(weight_kg)
    value = D(value)
    if weight_kg <= 0:
        raise ValidationError("Weight must be positive.")

    with transaction.atomic():
        v = None
        if value > 0:
            v = post_voucher(
                date=date, vtype='SHRINKAGE',
                narration=reason or f"Shrinkage {weight_kg}kg {item.name}",
                business=BUSINESS, source_module='chicken_center.shrinkage', user=user,
                lines=[
                    {'account': _acc('SHRINKAGE'), 'debit': value},
                    {'account': _acc('STOCK'), 'credit': value},
                ],
            )
        record_movement(item=item, mtype='SHRINKAGE_OUT', qty=weight_kg,
                        unit=item.base_unit, date=date, business=BUSINESS,
                        voucher=v, source_module='chicken_center.shrinkage')
        return Shrinkage.objects.create(
            item=item, date=date, weight_kg=weight_kg, value=value,
            reason=reason, voucher=v, created_by=user,
        )


# ──────────────────────── REVERSAL ──────────────────────────

def reverse_transaction(voucher, user=None):
    """Undo a chicken-center transaction: reverse money and stock together,
    and unwind any bill allocations so pending amounts stay correct."""
    from ..models import Sale, Collection, Allocation

    with transaction.atomic():
        # If reversing a COLLECTION: undo its allocations (bills go back to due).
        coll = Collection.objects.filter(voucher=voucher).first()
        if coll:
            for alloc in coll.allocations.select_related('sale'):
                bill = alloc.sale
                bill.amount_received -= alloc.amount
                if bill.amount_received < 0:
                    bill.amount_received = D(0)
                bill.recompute_status()
                bill.save(update_fields=['amount_received', 'status'])
            coll.allocations.all().delete()

        # If reversing a SALE (bill): drop allocations pointing at it; the
        # money that was applied becomes advance on the paying collections.
        sale = Sale.objects.filter(voucher=voucher).first()
        if sale:
            for alloc in sale.allocations.select_related('collection'):
                c = alloc.collection
                c.advance += alloc.amount
                c.save(update_fields=['advance'])
            sale.allocations.all().delete()

        reverse_movements_for_voucher(voucher)
        return reverse_voucher(voucher, user=user)


# ──────────────────── OPENING BALANCES ──────────────────────

def set_party_opening(*, party, amount, as_of, user=None):
    """Record a party's opening balance as an OPENING voucher.
    Positive = they owe us (Dr party / Cr Opening Balance Equity).
    Negative = we owe them (Dr OBE / Cr party).

    This affects the party's overall balance immediately. It is intentionally
    a plain voucher, not a bill: collections reduce the overall balance, so an
    opening receivable gets paid down naturally. Bill-wise 'pending bills' and
    ageing only track actual sale bills."""
    amount = D(amount)
    if amount == 0:
        raise ValidationError("Opening balance cannot be zero.")

    obe = _acc('OBE')
    ctrl = party.control_account
    if amount > 0:
        lines = [{'account': ctrl, 'party': party, 'debit': amount},
                 {'account': obe, 'credit': amount}]
    else:
        lines = [{'account': obe, 'debit': -amount},
                 {'account': ctrl, 'party': party, 'credit': -amount}]
    return post_voucher(
        date=as_of, vtype='OPENING',
        narration=f"Opening balance — {party.name}",
        business=BUSINESS, source_module='chicken_center.opening',
        user=user, lines=lines,
    )
    """Opening balance for a cash/bank account (Dr account / Cr OBE)."""
    amount = D(amount)
    if amount == 0:
        raise ValidationError("Opening balance cannot be zero.")
    acc = _acc(account_code)
    obe = _acc('OBE')
    with transaction.atomic():
        if amount > 0:
            lines = [{'account': acc, 'debit': amount}, {'account': obe, 'credit': amount}]
        else:
            lines = [{'account': obe, 'debit': -amount}, {'account': acc, 'credit': -amount}]
        return post_voucher(
            date=as_of, vtype='OPENING',
            narration=f"Opening balance — {acc.name}",
            business=BUSINESS, source_module='chicken_center.opening',
            user=user, lines=lines,
        )


def set_cash_opening(*, account_code, amount, as_of, user=None):
    """Opening balance for a cash/bank account (Dr account / Cr OBE)."""
    amount = D(amount)
    if amount == 0:
        raise ValidationError("Opening balance cannot be zero.")
    acc = _acc(account_code)
    obe = _acc('OBE')
    if amount > 0:
        lines = [{'account': acc, 'debit': amount}, {'account': obe, 'credit': amount}]
    else:
        lines = [{'account': obe, 'debit': -amount}, {'account': acc, 'credit': -amount}]
    return post_voucher(
        date=as_of, vtype='OPENING',
        narration=f"Opening balance — {acc.name}",
        business=BUSINESS, source_module='chicken_center.opening',
        user=user, lines=lines,
    )
