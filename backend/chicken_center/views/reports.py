from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounting.models import Voucher
from ..models import Sale
from ..serializers import SaleSerializer


# ─── PENDING BILLS (open sales, oldest-first) ───

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_bills(request):
    """Open bills (pending/partly), oldest-first. Filter by ?party=<id>."""
    qs = (Sale.objects
          .filter(status__in=['PENDING', 'PARTLY'])
          .exclude(voucher__is_reversed=True)
          .select_related('party')
          .order_by('date', 'id'))
    party = request.query_params.get('party')
    if party:
        qs = qs.filter(party_id=party)
    rows = [{
        'id': s.id, 'date': s.date, 'party_id': s.party_id,
        'party_name': s.party.name, 'amount': s.amount,
        'amount_received': s.amount_received, 'amount_due': s.amount_due,
        'status': s.status,
    } for s in qs]
    total_due = sum((r['amount_due'] for r in rows), 0)
    return Response({'rows': rows, 'total_due': total_due})


# ─── AGEING (how old are the pending dues) ───

def compute_ageing():
    """Pending bill dues bucketed by age (0-7/8-15/16-30/31+), grouped per
    customer, oldest-first, with column and grand totals. Plain function so
    both the API view and the Excel export can call it."""
    from datetime import date as date_cls
    from decimal import Decimal
    today = date_cls.today()
    buckets = ['0-7', '8-15', '16-30', '31+']

    qs = (Sale.objects
          .filter(status__in=['PENDING', 'PARTLY'])
          .exclude(voucher__is_reversed=True)
          .select_related('party')
          .order_by('party__name', 'date', 'id'))

    def bucket_of(days):
        if days <= 7:
            return '0-7'
        if days <= 15:
            return '8-15'
        if days <= 30:
            return '16-30'
        return '31+'

    per_party = {}
    for s in qs:
        days = (today - s.date).days
        b = bucket_of(days)
        row = per_party.setdefault(s.party_id, {
            'party_id': s.party_id, 'party_name': s.party.name,
            'phone': s.party.phone,
            '0-7': Decimal('0'), '8-15': Decimal('0'),
            '16-30': Decimal('0'), '31+': Decimal('0'),
            'total': Decimal('0'), 'oldest_days': 0,
        })
        row[b] += s.amount_due
        row['total'] += s.amount_due
        row['oldest_days'] = max(row['oldest_days'], days)

    rows = sorted(per_party.values(), key=lambda r: -r['oldest_days'])
    totals = {b: sum((r[b] for r in rows), Decimal('0')) for b in buckets}
    grand = sum((r['total'] for r in rows), Decimal('0'))
    return {'buckets': buckets, 'rows': rows, 'totals': totals, 'grand_total': grand}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ageing(request):
    return Response(compute_ageing())


# ─── SINGLE SALE (for invoice) ───

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sale_detail(request, pk):
    """One sale with everything an invoice needs: line, customer, seller,
    this bill's paid/due, and the customer's overall balance."""
    try:
        s = Sale.objects.select_related('party', 'item').get(pk=pk)
    except Sale.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
    data = SaleSerializer(s).data
    data['party_phone'] = s.party.phone
    data['party_address'] = s.party.address
    data['party_overall_balance'] = s.party.balance()
    data['is_reversed'] = bool(s.voucher and s.voucher.is_reversed)
    return Response(data)


# ─── DAYBOOK (everything on a date) ───

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daybook(request):
    """All vouchers for a given date (default today), any type, with amount."""
    from accounting.models import Voucher
    from datetime import date as date_cls
    day = request.query_params.get('date') or date_cls.today().isoformat()
    vs = (Voucher.objects
          .filter(business='chicken_center', date=day)
          .exclude(is_reversed=True)
          .prefetch_related('entries', 'entries__party')
          .order_by('id'))
    rows = []
    for v in vs:
        party = None
        for e in v.entries.all():
            if e.party:
                party = e.party.name
                break
        rows.append({
            'id': v.id, 'type': v.type, 'narration': v.narration,
            'party': party, 'amount': v.total_debit,
        })
    total = sum((r['amount'] for r in rows), 0)
    return Response({'date': day, 'rows': rows, 'total': total})


# ─── SALES SUMMARY (customer-wise / item-wise) ───

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_summary(request):
    """Sales totals grouped by customer and by item over a date range."""
    from datetime import date as date_cls
    from decimal import Decimal
    df = request.query_params.get('from') or date_cls.today().replace(day=1).isoformat()
    dt = request.query_params.get('to') or date_cls.today().isoformat()

    qs = (Sale.objects
          .filter(date__gte=df, date__lte=dt)
          .exclude(voucher__is_reversed=True)
          .select_related('party')
          .prefetch_related('lines', 'lines__item'))

    by_cust, by_item = {}, {}
    grand_amt = Decimal('0')
    grand_wt = Decimal('0')
    for s in qs:
        c = by_cust.setdefault(s.party_id, {'name': s.party.name, 'weight': Decimal('0'), 'amount': Decimal('0'), 'bills': 0})
        c['amount'] += s.amount
        c['bills'] += 1
        grand_amt += s.amount
        # weight and item breakdown come from lines (works for single + multi)
        for ln in s.lines.all():
            c['weight'] += ln.weight_kg
            grand_wt += ln.weight_kg
            it = by_item.setdefault(ln.item_id, {'name': ln.item.name, 'weight': Decimal('0'), 'amount': Decimal('0'), 'bills': 0})
            it['weight'] += ln.weight_kg
            it['amount'] += ln.amount
            it['bills'] += 1

    cust_rows = sorted(by_cust.values(), key=lambda r: -r['amount'])
    item_rows = sorted(by_item.values(), key=lambda r: -r['amount'])
    return Response({
        'date_from': df, 'date_to': dt,
        'by_customer': cust_rows, 'by_item': item_rows,
        'grand_amount': grand_amt, 'grand_weight': grand_wt,
    })
