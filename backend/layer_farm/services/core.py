"""
Layer Farm services — coordinate the accounting core (post_voucher) and
inventory (record_movement), and accumulate per-flock cost (FlockCost rows).

Pattern mirrors chicken_center: each action is atomic; money + stock + flock
cost move together. WhatsApp fires after commit, best-effort.
"""
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.db.models import Sum as models_Sum
from django.core.exceptions import ValidationError
from accounting.models import Account, Party
from accounting.services import post_voucher, reverse_voucher
from inventory.models import Item
from inventory.services import record_movement, reverse_movements_for_voucher
from ..models import (
    BUSINESS, LayerFlock, FlockCost, Purchase, FeedBatch, FeedBatchInput,
    FeedToFlock, Application, EggSale, Collection, Allocation, Payment, Expense,
)
# WhatsApp — reuse chicken_center's pluggable sender/messages.
from chicken_center.services import whatsapp as wa

EGGS_PER_TRAY = 30


def D(v):
    return Decimal(str(v))


def _acc(code):
    return Account.objects.get(code=code)


def _charge_flock(flock, date, category, amount, note='', voucher=None):
    """Add a cost line to a flock."""
    FlockCost.objects.create(flock=flock, date=date, category=category,
                             amount=D(amount), note=note, voucher=voucher)


# ───────────────────── PURCHASES (from vendor) ─────────────────────

_PUR_ACCOUNT = {
    'RAW': 'RAWPUR', 'PREMIX': 'PREMIXPUR', 'MEDICINE': 'MEDPUR',
    'VACCINE': 'VACCINEPUR', 'CHICK': 'CHICKPUR',
}
_PUR_STOCK_IN = {'RAW', 'PREMIX', 'MEDICINE', 'VACCINE'}  # these add to item stock


def create_purchase(*, vendor, kind, date, qty, rate, item=None, unit=None,
                    flock=None, note='', user=None):
    """Buy an input from a vendor. Dr <input purchases> / Cr vendor.
    RAW/PREMIX/MEDICINE/VACCINE add to the item's stock. CHICK is charged
    directly to the flock's cost."""
    qty = D(qty); rate = D(rate)
    if qty <= 0 or rate <= 0:
        raise ValidationError("Quantity and rate must be positive.")
    amount = (qty * rate).quantize(Decimal('0.01'))
    exp = _acc(_PUR_ACCOUNT[kind])

    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='PURCHASE',
            narration=f"{kind} from {vendor.name}",
            business=BUSINESS, source_module='layer.purchase', user=user,
            lines=[{'account': exp, 'debit': amount},
                   {'account': _acc('CREDITORS'), 'party': vendor, 'credit': amount}],
        )
        if kind in _PUR_STOCK_IN and item:
            record_movement(item=item, mtype='PURCHASE_IN', qty=qty,
                            unit=unit or item.base_unit, date=date,
                            business=BUSINESS, voucher=v,
                            source_module='layer.purchase')
        if kind == 'CHICK':
            if not flock:
                raise ValidationError("Chick purchase must be tagged to a flock.")
            _charge_flock(flock, date, 'CHICK', amount,
                          note=f"{int(qty)} chicks", voucher=v)
        return Purchase.objects.create(
            vendor=vendor, kind=kind, item=item, flock=flock, date=date,
            qty=qty, unit=unit, rate=rate, amount=amount, note=note,
            voucher=v, created_by=user,
        )


# ───────────────────── FEED BATCH (production) ─────────────────────

def create_feed_batch(*, date, feed_item, output_kg, inputs, overhead=0,
                      note='', user=None):
    """Mill run: consume raw materials -> produce feed. inputs is a list of
    {item, qty_kg, cost}. Batch cost = sum(input costs) + overhead; feed carries
    cost_per_kg = total / output. Accounting: Dr Finished Feed Stock / Cr Raw
    Material Stock (materials) + Cr Milling overhead source."""
    output_kg = D(output_kg)
    overhead = D(overhead)
    if output_kg <= 0:
        raise ValidationError("Output kg must be positive.")
    if not inputs:
        raise ValidationError("A feed batch needs at least one material.")

    # Each material must have enough stock on hand.
    for i in inputs:
        need = D(i['qty_kg'])
        have = raw_on_hand(i['item'])
        if need > have:
            raise ValidationError(
                f"Only {have} of {i['item'].name} in stock. Cannot consume {need}. "
                f"Buy more (Purchase) first.")

    materials_cost = sum((D(i['cost']) for i in inputs), Decimal('0'))
    total_cost = (materials_cost + overhead).quantize(Decimal('0.01'))
    cost_per_kg = (total_cost / output_kg).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

    with transaction.atomic():
        # Value moves from raw stock (+ overhead) into finished feed stock.
        lines = [{'account': _acc('FINSTOCK'), 'debit': total_cost},
                 {'account': _acc('RAWSTOCK'), 'credit': materials_cost}]
        if overhead > 0:
            lines.append({'account': _acc('MILLING'), 'credit': overhead})
        # If materials_cost is 0 (edge), the credit side still balances via overhead.
        v = post_voucher(
            date=date, vtype='PRODUCTION',
            narration=f"Feed batch: {output_kg}kg {feed_item.name}",
            business=BUSINESS, source_module='layer.feedbatch', user=user,
            lines=lines,
        )
        # Consume each raw material from stock; produce feed into stock.
        for i in inputs:
            record_movement(item=i['item'], mtype='CONSUME_OUT', qty=D(i['qty_kg']),
                            unit=i['item'].base_unit, date=date, business=BUSINESS,
                            voucher=v, source_module='layer.feedbatch')
        record_movement(item=feed_item, mtype='PRODUCE_IN', qty=output_kg,
                        unit=feed_item.base_unit, date=date, business=BUSINESS,
                        voucher=v, source_module='layer.feedbatch')

        batch = FeedBatch.objects.create(
            date=date, feed_item=feed_item, output_kg=output_kg,
            materials_cost=materials_cost, overhead_cost=overhead,
            total_cost=total_cost, cost_per_kg=cost_per_kg, note=note,
            voucher=v, created_by=user,
        )
        for i in inputs:
            FeedBatchInput.objects.create(batch=batch, item=i['item'],
                                          qty_kg=D(i['qty_kg']), cost=D(i['cost']))
        return batch


def feed_on_hand(feed_item):
    """Feed produced minus feed sent to flocks (reversals excluded)."""
    from ..models import FeedBatch, FeedToFlock
    produced = FeedBatch.objects.filter(feed_item=feed_item).exclude(
        voucher__is_reversed=True).aggregate(t=models_Sum('output_kg'))['t'] or Decimal('0')
    sent = FeedToFlock.objects.filter(feed_item=feed_item).exclude(
        voucher__is_reversed=True).aggregate(t=models_Sum('qty_kg'))['t'] or Decimal('0')
    return produced - sent


def raw_on_hand(item):
    """Raw material stock on hand, from inventory movements."""
    return item.stock_on_hand(business=BUSINESS)


def egg_stock_on_hand(flock):
    """Eggs available for a flock = laid - broken - sold (in eggs)."""
    return flock.egg_stock


def feed_batch_cost(feed_item):
    """Weighted-average cost per kg of feed made so far (for valuing transfers
    when no specific batch is chosen). Falls back to latest batch."""
    batches = FeedBatch.objects.filter(feed_item=feed_item)
    tot_kg = sum((b.output_kg for b in batches), Decimal('0'))
    tot_cost = sum((b.total_cost for b in batches), Decimal('0'))
    if tot_kg > 0:
        return (tot_cost / tot_kg).quantize(Decimal('0.0001'))
    return Decimal('0')


# ───────────────────── FEED -> FLOCK (at batch cost) ─────────────────────

def send_feed_to_flock(*, flock, feed_item, date, qty_kg, cost_per_kg=None,
                       note='', user=None):
    """Transfer made feed to a flock, valued at batch cost/kg. Dr Flock WIP /
    Cr Finished Feed Stock. Charges the flock's cost."""
    qty_kg = D(qty_kg)
    if qty_kg <= 0:
        raise ValidationError("Quantity must be positive.")
    avail = feed_on_hand(feed_item)
    if qty_kg > avail:
        raise ValidationError(
            f"Only {avail} kg of {feed_item.name} in stock. Cannot send {qty_kg} kg. "
            f"Produce more in the Feed Mill first.")
    cpk = D(cost_per_kg) if cost_per_kg is not None else feed_batch_cost(feed_item)
    amount = (qty_kg * cpk).quantize(Decimal('0.01'))

    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='JOURNAL',
            narration=f"Feed to {flock.name}: {qty_kg}kg",
            business=BUSINESS, source_module='layer.feedtoflock', user=user,
            lines=[{'account': _acc('FLOCKWIP'), 'debit': amount},
                   {'account': _acc('FINSTOCK'), 'credit': amount}],
        )
        record_movement(item=feed_item, mtype='SALE_OUT', qty=qty_kg,
                        unit=feed_item.base_unit, date=date, business=BUSINESS,
                        voucher=v, source_module='layer.feedtoflock')
        _charge_flock(flock, date, 'FEED', amount, note=note, voucher=v)
        return FeedToFlock.objects.create(
            flock=flock, feed_item=feed_item, date=date, qty_kg=qty_kg,
            cost_per_kg=cpk, amount=amount, note=note, voucher=v, created_by=user,
        )


# ───────────────────── APPLY medicine/vaccine/premix ─────────────────────

def apply_to_flock(*, flock, kind, date, amount, item=None, qty=0, note='', user=None):
    """Administer medicine/vaccine/premix to a flock. Dr Flock WIP / Cr Stock
    (value), reduce item stock if tracked, charge the flock."""
    amount = D(amount)
    if amount <= 0:
        raise ValidationError("Amount must be positive.")
    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='JOURNAL',
            narration=f"{kind} to {flock.name}",
            business=BUSINESS, source_module='layer.application', user=user,
            lines=[{'account': _acc('FLOCKWIP'), 'debit': amount},
                   {'account': _acc('STOCK'), 'credit': amount}],
        )
        if item and D(qty) > 0:
            record_movement(item=item, mtype='SALE_OUT', qty=D(qty),
                            unit=item.base_unit, date=date, business=BUSINESS,
                            voucher=v, source_module='layer.application')
        _charge_flock(flock, date, kind, amount, note=note, voucher=v)
        return Application.objects.create(
            flock=flock, kind=kind, item=item, date=date, qty=D(qty),
            amount=amount, note=note, voucher=v, created_by=user,
        )


# ───────────────────── EXPENSE (split across flocks) ─────────────────────

def create_expense(*, date, account_code, amount, mode='CASH',
                   split_across_flocks=True, flock=None, note='', user=None):
    """General expense. Dr <expense head> / Cr Cash. Then charge it to flock
    cost — to one flock, or split across active flocks by bird-count share."""
    amount = D(amount)
    if amount <= 0:
        raise ValidationError("Amount must be positive.")
    exp = _acc(account_code)
    if exp.type != 'EXPENSE':
        raise ValidationError(f"{account_code} is not an expense account.")
    mode_acc = {'CASH': 'CASH', 'UPI': 'UPI', 'BANK': 'BANK'}[mode]

    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='EXPENSE', narration=note or exp.name,
            business=BUSINESS, source_module='layer.expense', user=user,
            lines=[{'account': exp, 'debit': amount},
                   {'account': _acc(mode_acc), 'credit': amount}],
        )
        category = 'LABOUR' if account_code == 'LABOUR' else 'OVERHEAD'
        if flock:
            _charge_flock(flock, date, category, amount, note=note, voucher=v)
        elif split_across_flocks:
            active = list(LayerFlock.objects.filter(status='ACTIVE'))
            total_birds = sum(f.live_birds for f in active) or 0
            if active and total_birds > 0:
                allocated = Decimal('0')
                for i, f in enumerate(active):
                    if i == len(active) - 1:
                        share = amount - allocated  # last gets remainder
                    else:
                        share = (amount * D(f.live_birds) / D(total_birds)).quantize(Decimal('0.01'))
                        allocated += share
                    if share > 0:
                        _charge_flock(f, date, category, share,
                                      note=f"{note} (split)", voucher=v)
        return Expense.objects.create(
            date=date, account_code=account_code, amount=amount, mode=mode,
            split_across_flocks=split_across_flocks, note=note, voucher=v,
            created_by=user,
        )


# ───────────────────── EGG SALE + settlement ─────────────────────

def create_egg_sale(*, party, flock, date, trays, rate_per_tray, note='', user=None):
    """Sell eggs (trays) to a trader, tagged to a flock. Dr trader / Cr Egg
    Sales. Reduces egg stock conceptually (tracked via flock)."""
    trays = D(trays); rate = D(rate_per_tray)
    if trays <= 0 or rate <= 0:
        raise ValidationError("Trays and rate must be positive.")
    eggs_needed = trays * EGGS_PER_TRAY
    available = egg_stock_on_hand(flock)
    if eggs_needed > available:
        avail_trays = round(available / EGGS_PER_TRAY, 2)
        raise ValidationError(
            f"Only {available} eggs ({avail_trays} trays) in stock for {flock.name}. "
            f"Cannot sell {trays} trays. Record daily egg production first.")
    amount = (trays * rate).quantize(Decimal('0.01'))

    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='SALE',
            narration=f"Egg sale to {party.name}: {trays} trays",
            business=BUSINESS, source_module='layer.eggsale', user=user,
            lines=[{'account': _acc('DEBTORS'), 'party': party, 'debit': amount},
                   {'account': _acc('EGGSALES'), 'credit': amount}],
        )
        sale = EggSale.objects.create(
            party=party, flock=flock, date=date, trays=trays,
            rate_per_tray=rate, amount=amount, note=note, voucher=v, created_by=user,
        )
    balance = party.balance()
    res = wa.send_whatsapp(party.phone, wa.build_sale_message(
        customer_name=party.name, weight_kg=f"{trays} trays", amount=amount, balance=balance))
    EggSale.objects.filter(id=sale.id).update(whatsapp_status=res['status'])
    sale.whatsapp_status = res['status']
    return sale


def create_collection(*, party, date, amount, mode='CASH', note='', user=None):
    """Money from a trader; settles egg-sale bills oldest-first; excess held
    as advance; WhatsApp receipt."""
    amount = D(amount)
    if amount <= 0:
        raise ValidationError("Amount must be positive.")
    mode_acc = {'CASH': 'CASH', 'UPI': 'UPI', 'BANK': 'BANK'}[mode]

    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='RECEIPT',
            narration=f"Received from {party.name} ({mode})",
            business=BUSINESS, source_module='layer.collection', user=user,
            lines=[{'account': _acc(mode_acc), 'debit': amount},
                   {'account': _acc('DEBTORS'), 'party': party, 'credit': amount}],
        )
        coll = Collection.objects.create(
            party=party, date=date, amount=amount, mode=mode, note=note,
            voucher=v, created_by=user,
        )
        remaining = amount
        pending = (EggSale.objects
                   .filter(party=party, status__in=['PENDING', 'PARTLY'])
                   .exclude(voucher__is_reversed=True)
                   .order_by('date', 'id').select_for_update())
        for bill in pending:
            if remaining <= 0:
                break
            due = bill.amount_due
            if due <= 0:
                continue
            applied = min(due, remaining)
            Allocation.objects.create(collection=coll, egg_sale=bill, amount=applied)
            bill.amount_received += applied
            bill.recompute_status()
            bill.save(update_fields=['amount_received', 'status'])
            remaining -= applied
        if remaining > 0:
            coll.advance = remaining
            coll.save(update_fields=['advance'])

    balance = party.balance()
    res = wa.send_whatsapp(party.phone, wa.build_collection_message(
        customer_name=party.name, amount=amount, mode=mode, balance=balance))
    Collection.objects.filter(id=coll.id).update(whatsapp_status=res['status'])
    coll.whatsapp_status = res['status']
    return coll


def create_payment(*, party, date, amount, mode='CASH', note='', user=None):
    """Pay a vendor. Dr vendor / Cr Cash."""
    amount = D(amount)
    if amount <= 0:
        raise ValidationError("Amount must be positive.")
    mode_acc = {'CASH': 'CASH', 'UPI': 'UPI', 'BANK': 'BANK'}[mode]
    with transaction.atomic():
        v = post_voucher(
            date=date, vtype='PAYMENT', narration=f"Paid {party.name} ({mode})",
            business=BUSINESS, source_module='layer.payment', user=user,
            lines=[{'account': _acc('CREDITORS'), 'party': party, 'debit': amount},
                   {'account': _acc(mode_acc), 'credit': amount}],
        )
        return Payment.objects.create(
            party=party, date=date, amount=amount, mode=mode, note=note,
            voucher=v, created_by=user,
        )


# ───────────────────── REVERSAL ─────────────────────

def reverse_transaction(voucher, user=None):
    """Undo a layer transaction: money, stock, flock-cost, and bill allocations
    together."""
    with transaction.atomic():
        # Collection: undo allocations
        coll = Collection.objects.filter(voucher=voucher).first()
        if coll:
            for a in coll.allocations.select_related('egg_sale'):
                b = a.egg_sale
                b.amount_received -= a.amount
                if b.amount_received < 0:
                    b.amount_received = D(0)
                b.recompute_status()
                b.save(update_fields=['amount_received', 'status'])
            coll.allocations.all().delete()
        # Egg sale reversed: drop allocations pointing to it -> advance
        sale = EggSale.objects.filter(voucher=voucher).first()
        if sale:
            for a in sale.allocations.select_related('collection'):
                c = a.collection
                c.advance += a.amount
                c.save(update_fields=['advance'])
            sale.allocations.all().delete()
        # Remove any flock-cost lines tied to this voucher
        FlockCost.objects.filter(voucher=voucher).delete()
        reverse_movements_for_voucher(voucher)
        return reverse_voucher(voucher, user=user)


# ───────────────────── OPENING BALANCES ─────────────────────

def set_party_opening(*, party, amount, as_of, user=None):
    """Opening balance for a vendor/trader. +ve = they owe us (Dr party /
    Cr OBE); -ve = we owe them. Plain voucher affecting overall balance."""
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
        date=as_of, vtype='OPENING', narration=f"Opening balance — {party.name}",
        business=BUSINESS, source_module='layer.opening', user=user, lines=lines)


def set_cash_opening(*, account_code, amount, as_of, user=None):
    """Opening balance for cash/bank (Dr account / Cr OBE)."""
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
        date=as_of, vtype='OPENING', narration=f"Opening balance — {acc.name}",
        business=BUSINESS, source_module='layer.opening', user=user, lines=lines)
