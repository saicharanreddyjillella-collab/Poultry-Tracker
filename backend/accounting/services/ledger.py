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


def pnl_detailed(date_from, date_to, business=None):
    """P&L with per-account breakdown of income and expense lines."""
    def lines_for(atype):
        rows = []
        qs = Entry.objects.filter(
            account__type=atype,
            voucher__date__gte=date_from, voucher__date__lte=date_to,
        )
        if business:
            qs = qs.filter(voucher__business=business)
        by_acc = {}
        for e in qs.select_related('account'):
            amt = (e.credit - e.debit) if atype == 'INCOME' else (e.debit - e.credit)
            key = (e.account.code, e.account.name)
            by_acc[key] = by_acc.get(key, Decimal('0')) + amt
        for (code, name), amt in sorted(by_acc.items(), key=lambda x: -x[1]):
            if amt != 0:
                rows.append({'code': code, 'name': name, 'amount': amt})
        return rows

    income_lines = lines_for('INCOME')
    expense_lines = lines_for('EXPENSE')
    income = sum((r['amount'] for r in income_lines), Decimal('0'))
    expense = sum((r['amount'] for r in expense_lines), Decimal('0'))
    return {
        'date_from': date_from, 'date_to': date_to,
        'income_lines': income_lines, 'expense_lines': expense_lines,
        'income': income, 'expense': expense, 'profit': income - expense,
    }


def cash_book(date_from, date_to, accounts=('CASH', 'UPI', 'BANK'), business=None):
    """Money movement through cash/bank accounts over a period, with opening
    and closing balances. Each row is one entry hitting a cash account."""
    result = {}
    for code in accounts:
        try:
            acc = Account.objects.get(code=code)
        except Account.DoesNotExist:
            continue

        # Opening = balance strictly before date_from
        opening_qs = acc.entries.filter(voucher__date__lt=date_from)
        if business:
            opening_qs = opening_qs.filter(voucher__business=business)
        oa = opening_qs.aggregate(d=Sum('debit'), c=Sum('credit'))
        opening = (oa['d'] or Decimal('0')) - (oa['c'] or Decimal('0'))  # asset: debit-normal

        period_qs = acc.entries.filter(
            voucher__date__gte=date_from, voucher__date__lte=date_to,
        ).select_related('voucher', 'party').order_by('voucher__date', 'id')
        if business:
            period_qs = period_qs.filter(voucher__business=business)

        running = opening
        rows = []
        receipts = Decimal('0')
        payments = Decimal('0')
        for e in period_qs:
            running += (e.debit - e.credit)
            receipts += e.debit
            payments += e.credit
            rows.append({
                'date': e.voucher.date,
                'type': e.voucher.type,
                'party': e.party.name if e.party else None,
                'narration': e.voucher.narration,
                'in': e.debit,
                'out': e.credit,
                'balance': running,
            })
        result[code] = {
            'account': acc.name,
            'opening': opening,
            'receipts': receipts,
            'payments': payments,
            'closing': running,
            'rows': rows,
        }
    return result


def balance_sheet(upto=None, business=None):
    """Assets vs Liabilities + Equity as of a date. Profit for the period
    (Income − Expense) rolls into equity as 'Current Period Earnings' so the
    sheet balances."""
    from .ledger import trial_balance  # local import to reuse net balances
    accounts = Account.objects.filter(active=True)

    def net(acc):
        qs = acc.entries.all()
        if upto:
            qs = qs.filter(voucher__date__lte=upto)
        if business:
            qs = qs.filter(voucher__business=business)
        agg = qs.aggregate(d=Sum('debit'), c=Sum('credit'))
        d = agg['d'] or Decimal('0')
        c = agg['c'] or Decimal('0')
        return d - c  # raw debit-minus-credit

    assets, liabilities, equity = [], [], []
    total_assets = total_liab = total_equity = Decimal('0')
    income_total = expense_total = Decimal('0')

    for acc in accounts:
        n = net(acc)
        if acc.type == 'ASSET':
            if n != 0:
                assets.append({'code': acc.code, 'name': acc.name, 'amount': n})
                total_assets += n
        elif acc.type == 'LIABILITY':
            if -n != 0:
                liabilities.append({'code': acc.code, 'name': acc.name, 'amount': -n})
                total_liab += -n
        elif acc.type == 'EQUITY':
            if -n != 0:
                equity.append({'code': acc.code, 'name': acc.name, 'amount': -n})
                total_equity += -n
        elif acc.type == 'INCOME':
            income_total += -n  # credit-normal
        elif acc.type == 'EXPENSE':
            expense_total += n   # debit-normal

    # Net profit for the period folds into equity.
    current_earnings = income_total - expense_total
    if current_earnings != 0:
        equity.append({'code': 'EARNINGS', 'name': 'Current Period Earnings',
                       'amount': current_earnings})
        total_equity += current_earnings

    return {
        'assets': assets, 'liabilities': liabilities, 'equity': equity,
        'total_assets': total_assets,
        'total_liabilities': total_liab,
        'total_equity': total_equity,
        'total_liab_equity': total_liab + total_equity,
        'balanced': total_assets == (total_liab + total_equity),
    }
