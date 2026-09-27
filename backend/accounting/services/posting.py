"""
The posting service — the ONE way money enters the ledger.

Every business module calls post_voucher(). It enforces double-entry balance
and writes atomically, so a voucher posts completely or not at all. Users
never see debit/credit — modules build the lines, this guarantees integrity.

This module is PURE accounting: it knows nothing about stock or items.
When a business event moves both money and stock, the business module makes
two coordinated calls — post_voucher() here and record_movement() in
inventory — passing the voucher to link them.
"""
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import Account, Voucher, Entry, AuditLog, BookLock


def D(v):
    return Decimal(str(v))


def _check_not_locked(business, vdate):
    """Reject any posting/reversal dated on or before the book-close date."""
    closed = BookLock.closed_date_for(business)
    if closed and vdate <= closed:
        raise ValidationError(
            f"Books for this business are closed through {closed}. "
            f"Cannot post or change anything dated {vdate}. Ask an admin to re-open if needed."
        )


@transaction.atomic
def post_voucher(*, date, vtype, narration, lines, business='chicken_center',
                 source_module='', source_ref='', user=None):
    """
    Post a balanced voucher.

    lines: list of dicts, each:
        {'account': Account|code, 'party': Party|None, 'debit': x, 'credit': y}
      Exactly one of debit/credit non-zero per line. Sum(debit)==sum(credit).

    Returns the created Voucher.
    """
    if not lines:
        raise ValidationError("A voucher needs at least one line.")

    _check_not_locked(business, date)

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

    if user:
        AuditLog.objects.create(
            user=user, action='CREATE', object_type='Voucher',
            object_id=str(voucher.id),
            detail={'type': vtype, 'amount': str(total_debit), 'narration': narration},
        )
    return voucher


@transaction.atomic
def reverse_voucher(voucher, user=None):
    """Post an equal-and-opposite voucher to cancel one, and flag both.
    Corrections never edit history — they reverse it. Inventory movements
    linked to the voucher are reversed by the inventory service separately."""
    if voucher.is_reversed:
        raise ValidationError("Voucher already reversed.")

    _check_not_locked(voucher.business, voucher.date)

    rev = Voucher.objects.create(
        date=voucher.date, type=voucher.type,
        narration=f"REVERSAL of #{voucher.id}: {voucher.narration}",
        business=voucher.business, source_module=voucher.source_module,
        source_ref=voucher.source_ref, created_by=user, reverses=voucher,
    )
    for e in voucher.entries.all():
        Entry.objects.create(voucher=rev, account=e.account, party=e.party,
                             debit=e.credit, credit=e.debit)  # swapped

    voucher.is_reversed = True
    voucher.save(update_fields=['is_reversed'])

    if user:
        AuditLog.objects.create(
            user=user, action='REVERSE', object_type='Voucher',
            object_id=str(voucher.id), detail={'reversal_id': rev.id},
        )
    return rev
