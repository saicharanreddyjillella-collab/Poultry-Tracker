"""
Read-side accounting services — everything derived from entries, never stored.
Party statements, account ledgers, trial balance, P&L.
"""
from decimal import Decimal
from django.db.models import Sum
from ..models import Account, Party, Voucher, Entry


def party_ledger(party, date_from=None, date_to=None):
    """Passbook for a party: chronological entries with a running balance."""
    qs = Entry.objects.filter(party=party).select_related('voucher').order_by('voucher__date', 'id')
    if date_from:
        qs = qs.filter(voucher__date__gte=date_from)
    if date_to:
        qs = qs.filter(voucher__date__lte=date_to)

    running = Decimal('0')
    rows = []
    for e in qs:
        running += (e.debit - e.credit)
        rows.append({
            'date': e.voucher.date,
            'voucher_id': e.voucher_id,
            'type': e.voucher.type,
            'narration': e.voucher.narration,
            'debit': e.debit,
            'credit': e.credit,
            'balance': running,
        })
    return {'party': party.name, 'rows': rows, 'closing_balance': running}


def account_ledger(account, date_from=None, date_to=None, business=None):
    """All entries hitting an account with a running balance."""
    qs = account.entries.select_related('voucher', 'party').order_by('voucher__date', 'id')
    if date_from:
        qs = qs.filter(voucher__date__gte=date_from)
    if date_to:
        qs = qs.filter(voucher__date__lte=date_to)
    if business:
        qs = qs.filter(voucher__business=business)

    running = Decimal('0')
    sign = 1 if account.is_debit_normal else -1
    rows = []
    for e in qs:
        running += sign * (e.debit - e.credit)
        rows.append({
            'date': e.voucher.date,
            'voucher_id': e.voucher_id,
            'type': e.voucher.type,
            'party': e.party.name if e.party else None,
            'narration': e.voucher.narration,
            'debit': e.debit,
            'credit': e.credit,
            'balance': running,
        })
    return {'account': account.name, 'rows': rows, 'closing_balance': running}


def trial_balance(upto=None, business=None):
    """Every account's net debit/credit. Total debits must equal total credits."""
    accounts = Account.objects.filter(active=True)
    rows = []
    total_dr = Decimal('0')
    total_cr = Decimal('0')
    for acc in accounts:
        qs = acc.entries.all()
        if upto:
            qs = qs.filter(voucher__date__lte=upto)
        if business:
            qs = qs.filter(voucher__business=business)
        agg = qs.aggregate(d=Sum('debit'), c=Sum('credit'))
        d = agg['d'] or Decimal('0')
        c = agg['c'] or Decimal('0')
        net = d - c
        if net == 0:
            continue
        dr = net if net > 0 else Decimal('0')
        cr = -net if net < 0 else Decimal('0')
        total_dr += dr
        total_cr += cr
        rows.append({'code': acc.code, 'name': acc.name, 'type': acc.type,
                     'debit': dr, 'credit': cr})
    return {'rows': rows, 'total_debit': total_dr, 'total_credit': total_cr,
            'balanced': total_dr == total_cr}


def profit_and_loss(date_from, date_to, business=None):
    """Income − Expense over a period."""
    def total_for(atype):
        qs = Entry.objects.filter(
            account__type=atype,
            voucher__date__gte=date_from, voucher__date__lte=date_to,
        )
        if business:
            qs = qs.filter(voucher__business=business)
        agg = qs.aggregate(d=Sum('debit'), c=Sum('credit'))
        d = agg['d'] or Decimal('0')
        c = agg['c'] or Decimal('0')
        # Income is credit-normal, Expense is debit-normal
        return (c - d) if atype == 'INCOME' else (d - c)

    income = total_for('INCOME')
    expense = total_for('EXPENSE')
    return {
        'date_from': date_from, 'date_to': date_to,
        'income': income, 'expense': expense, 'profit': income - expense,
    }
