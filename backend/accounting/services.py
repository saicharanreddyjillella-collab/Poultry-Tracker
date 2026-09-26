"""
The posting service — the ONE way anything enters the ledger.

Every business module calls post_voucher(). It enforces double-entry balance
and writes everything inside a single atomic transaction, so a voucher either
posts completely or not at all. Users never see debit/credit — modules build
the lines, this function guarantees integrity.
"""
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from .models import Account, Party, Voucher, Entry, Unit, Item, StockMovement, AuditLog


def D(v):
    return Decimal(str(v))


@transaction.atomic
def post_voucher(*, date, vtype, narration, lines, business='chicken_center',
                 source_module='', source_ref='', user=None, stock_moves=None):
    """
    Post a balanced voucher.

    lines: list of dicts, each:
        {'account': Account|code, 'party': Party|None, 'debit': x, 'credit': y}
      Exactly one of debit/credit non-zero per line. Sum(debit)==sum(credit).

    stock_moves: optional list of dicts for inventory movement:
        {'item': Item, 'type': 'PURCHASE_IN'|..., 'qty': x, 'unit': Unit,
         'note': ''}

    Returns the created Voucher.
    """
    if not lines:
        raise ValidationError("A voucher needs at least one line.")

    resolved = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')

    for ln in lines:
        acc = ln['account']
        if isinstance(acc, str):
            acc = Account.objects.get(code=acc)
        debit = D(ln.get('debit', 0) or 0)
        credit = D(ln.get('credit', 0) or 0)
        if debit < 0 or credit < 0:
            raise ValidationError("Debit/credit cannot be negative.")
        if debit > 0 and credit > 0:
            raise ValidationError("A line cannot have both debit and credit.")
        if debit == 0 and credit == 0:
            raise ValidationError("A line must have a debit or a credit.")
        total_debit += debit
        total_credit += credit
        resolved.append((acc, ln.get('party'), debit, credit))

    if total_debit != total_credit:
        raise ValidationError(
            f"Voucher not balanced: debits {total_debit} != credits {total_credit}."
        )

    voucher = Voucher.objects.create(
        date=date, type=vtype, narration=narration, business=business,
        source_module=source_module, source_ref=source_ref, created_by=user,
    )
    for acc, party, debit, credit in resolved:
        Entry.objects.create(voucher=voucher, account=acc, party=party,
                             debit=debit, credit=credit)

    # Inventory movements, if any, tied to this voucher.
    if stock_moves:
        for m in stock_moves:
            _post_stock_movement(voucher=voucher, business=business,
                                 source_module=source_module,
                                 source_ref=source_ref, date=date, **m)

    if user:
        AuditLog.objects.create(
            user=user, action='CREATE', object_type='Voucher',
            object_id=str(voucher.id),
            detail={'type': vtype, 'amount': str(total_debit), 'narration': narration},
        )
    return voucher


IN_TYPES = {'PURCHASE_IN', 'PRODUCE_IN', 'ADJUST'}
OUT_TYPES = {'SALE_OUT', 'CONSUME_OUT', 'SHRINKAGE_OUT'}


def _post_stock_movement(*, voucher, business, source_module, source_ref,
                         date, item, type, qty, unit, note=''):
    """Record one stock movement, converting the entered quantity into the
    item's base unit so on-hand math stays consistent."""
    if isinstance(unit, str):
        unit = Unit.objects.get(symbol=unit)
    qty = D(qty)
    if qty < 0:
        raise ValidationError("Stock quantity cannot be negative.")

    # Convert entered unit → base unit of the item.
    # If the entered unit converts to the item's base unit, apply factor.
    base_qty = qty * (unit.factor_to_base if unit_id_differs(unit, item.base_unit) else Decimal('1'))

    qty_in = base_qty if type in IN_TYPES else Decimal('0')
    qty_out = base_qty if type in OUT_TYPES else Decimal('0')

    return StockMovement.objects.create(
        item=item, date=date, type=type,
        qty_in_base=qty_in, qty_out_base=qty_out,
        entered_qty=qty, entered_unit=unit, business=business,
        voucher=voucher, source_module=source_module, source_ref=source_ref,
        note=note,
    )


def unit_id_differs(entered_unit, base_unit):
    """True if the entered unit is a derived unit (bag) that must convert to
    the item's base unit (kg). If they're the same unit, no conversion."""
    return entered_unit.id != base_unit.id


@transaction.atomic
def reverse_voucher(voucher, user=None):
    """Post an equal-and-opposite voucher to cancel one, and flag both.
    Corrections never edit history — they reverse it."""
    if voucher.is_reversed:
        raise ValidationError("Voucher already reversed.")

    rev = Voucher.objects.create(
        date=voucher.date, type=voucher.type,
        narration=f"REVERSAL of #{voucher.id}: {voucher.narration}",
        business=voucher.business, source_module=voucher.source_module,
        source_ref=voucher.source_ref, created_by=user, reverses=voucher,
    )
    for e in voucher.entries.all():
        Entry.objects.create(voucher=rev, account=e.account, party=e.party,
                             debit=e.credit, credit=e.debit)  # swapped

    # Reverse any stock movements too.
    for sm in voucher.stock_movements.all():
        StockMovement.objects.create(
            item=sm.item, date=sm.date, type='ADJUST',
            qty_in_base=sm.qty_out_base, qty_out_base=sm.qty_in_base,
            entered_qty=sm.entered_qty, entered_unit=sm.entered_unit,
            business=sm.business, voucher=rev,
            note=f"Reversal of movement #{sm.id}",
        )

    voucher.is_reversed = True
    voucher.save(update_fields=['is_reversed'])

    if user:
        AuditLog.objects.create(
            user=user, action='REVERSE', object_type='Voucher',
            object_id=str(voucher.id), detail={'reversal_id': rev.id},
        )
    return rev
