"""
Inventory service — the ONE way stock moves.

record_movement() converts the entered quantity into the item's base unit and
writes a StockMovement. When a movement accompanies a money voucher, the
business module passes that voucher to link them. This app may read accounting
(to link a voucher) but accounting never imports inventory — the dependency
points one way only.
"""
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Unit, Item, StockMovement

IN_TYPES = {'PURCHASE_IN', 'PRODUCE_IN'}
OUT_TYPES = {'SALE_OUT', 'CONSUME_OUT', 'SHRINKAGE_OUT'}


def D(v):
    return Decimal(str(v))


@transaction.atomic
def record_movement(*, item, mtype, qty, unit, date, business='chicken_center',
                    voucher=None, source_module='', source_ref='', note=''):
    """Record one stock movement, converting the entered unit → the item's
    base unit so on-hand math stays consistent."""
    if isinstance(unit, str):
        unit = Unit.objects.get(symbol=unit)
    qty = D(qty)
    if qty < 0:
        raise ValidationError("Stock quantity cannot be negative.")

    # Convert to base unit of the item. If the entered unit is the item's own
    # base unit, no conversion; otherwise apply its factor_to_base.
    if unit.id == item.base_unit_id:
        base_qty = qty
    else:
        base_qty = qty * unit.factor_to_base

    if mtype in IN_TYPES:
        qty_in, qty_out = base_qty, Decimal('0')
    elif mtype in OUT_TYPES:
        qty_in, qty_out = Decimal('0'), base_qty
    elif mtype == 'ADJUST':
        # Positive qty = increase; caller may pass a negative via two calls.
        qty_in, qty_out = base_qty, Decimal('0')
    else:
        raise ValidationError(f"Unknown movement type: {mtype}")

    return StockMovement.objects.create(
        item=item, date=date, type=mtype,
        qty_in_base=qty_in, qty_out_base=qty_out,
        entered_qty=qty, entered_unit=unit, business=business,
        voucher=voucher, source_module=source_module, source_ref=source_ref,
        note=note,
    )


def stock_on_hand(item, business=None):
    """Convenience wrapper — current base-unit stock for an item."""
    return item.stock_on_hand(business=business)


@transaction.atomic
def reverse_movements_for_voucher(voucher):
    """Reverse every stock movement linked to a voucher (used when the money
    voucher is reversed). Each becomes an opposite ADJUST."""
    for sm in voucher.stock_movements.all():
        StockMovement.objects.create(
            item=sm.item, date=sm.date, type='ADJUST',
            qty_in_base=sm.qty_out_base, qty_out_base=sm.qty_in_base,
            entered_qty=sm.entered_qty, entered_unit=sm.entered_unit,
            business=sm.business, voucher=voucher,
            note=f"Reversal of movement #{sm.id}",
        )
