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
    """Dr Cash/UPI/Bank / Cr Customer, then WhatsApp receipt."""
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
    """Undo a chicken-center transaction: reverse money and stock together."""
    reverse_movements_for_voucher(voucher)
    return reverse_voucher(voucher, user=user)
