from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from datetime import date as date_cls

from accounting.models import Party
from inventory.models import Item
from .models import Sale, Purchase, Collection, Payment, Expense, Shrinkage
from .serializers import (
    SaleSerializer, PurchaseSerializer, CollectionSerializer,
    PaymentSerializer, ExpenseSerializer, ShrinkageSerializer,
)
from .services import (
    create_sale, create_purchase, create_collection, create_payment,
    create_expense, create_shrinkage, reverse_transaction,
)


def _err(e):
    msg = e.message_dict if hasattr(e, 'message_dict') else (
        e.messages[0] if hasattr(e, 'messages') else str(e))
    return Response({'error': msg}, status=400)


# ─── SALES ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def sales(request):
    if request.method == 'GET':
        qs = Sale.objects.select_related('party', 'item').all()
        party = request.query_params.get('party')
        if party:
            qs = qs.filter(party_id=party)
        return Response(SaleSerializer(qs, many=True).data)
    d = request.data
    try:
        sale = create_sale(
            party=Party.objects.get(id=d['party']),
            item=Item.objects.get(id=d['item']),
            date=d.get('date') or date_cls.today(),
            weight_kg=d['weight_kg'], rate_per_kg=d['rate_per_kg'],
            note=d.get('note', ''), user=request.user,
        )
        return Response(SaleSerializer(sale).data, status=201)
    except ValidationError as e:
        return _err(e)


# ─── PURCHASES ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def purchases(request):
    if request.method == 'GET':
        qs = Purchase.objects.select_related('party', 'item').all()
        return Response(PurchaseSerializer(qs, many=True).data)
    d = request.data
    try:
        p = create_purchase(
            party=Party.objects.get(id=d['party']),
            item=Item.objects.get(id=d['item']),
            date=d.get('date') or date_cls.today(),
            weight_kg=d['weight_kg'], rate_per_kg=d['rate_per_kg'],
            note=d.get('note', ''), user=request.user,
        )
        return Response(PurchaseSerializer(p).data, status=201)
    except ValidationError as e:
        return _err(e)


# ─── COLLECTIONS ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def collections(request):
    if request.method == 'GET':
        qs = Collection.objects.select_related('party').all()
        return Response(CollectionSerializer(qs, many=True).data)
    d = request.data
    try:
        c = create_collection(
            party=Party.objects.get(id=d['party']),
            date=d.get('date') or date_cls.today(),
            amount=d['amount'], mode=d.get('mode', 'CASH'),
            note=d.get('note', ''), user=request.user,
        )
        return Response(CollectionSerializer(c).data, status=201)
    except ValidationError as e:
        return _err(e)


# ─── PAYMENTS ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def payments(request):
    if request.method == 'GET':
        qs = Payment.objects.select_related('party').all()
        return Response(PaymentSerializer(qs, many=True).data)
    d = request.data
    try:
        p = create_payment(
            party=Party.objects.get(id=d['party']),
            date=d.get('date') or date_cls.today(),
            amount=d['amount'], mode=d.get('mode', 'CASH'),
            note=d.get('note', ''), user=request.user,
        )
        return Response(PaymentSerializer(p).data, status=201)
    except ValidationError as e:
        return _err(e)


# ─── EXPENSES ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def expenses(request):
    if request.method == 'GET':
        qs = Expense.objects.all()
        return Response(ExpenseSerializer(qs, many=True).data)
    d = request.data
    try:
        e = create_expense(
            date=d.get('date') or date_cls.today(),
            account_code=d['account_code'], amount=d['amount'],
            mode=d.get('mode', 'CASH'), note=d.get('note', ''), user=request.user,
        )
        return Response(ExpenseSerializer(e).data, status=201)
    except ValidationError as ex:
        return _err(ex)


# ─── SHRINKAGE ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def shrinkage(request):
    if request.method == 'GET':
        qs = Shrinkage.objects.select_related('item').all()
        return Response(ShrinkageSerializer(qs, many=True).data)
    d = request.data
    try:
        s = create_shrinkage(
            item=Item.objects.get(id=d['item']),
            date=d.get('date') or date_cls.today(),
            weight_kg=d['weight_kg'], value=d.get('value', 0),
            reason=d.get('reason', ''), user=request.user,
        )
        return Response(ShrinkageSerializer(s).data, status=201)
    except ValidationError as e:
        return _err(e)


# ─── REVERSE (undo a transaction: money + stock together) ───

_MODEL_MAP = {
    'sale': Sale, 'purchase': Purchase, 'collection': Collection,
    'payment': Payment, 'expense': Expense, 'shrinkage': Shrinkage,
}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reverse_entry(request, kind, pk):
    """Reverse a chicken-center transaction by kind + id. Posts an
    equal-and-opposite voucher and reverses linked stock. History is kept."""
    model = _MODEL_MAP.get(kind)
    if not model:
        return Response({'error': f'Unknown type: {kind}'}, status=400)
    try:
        obj = model.objects.select_related('voucher').get(pk=pk)
    except model.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
    if not obj.voucher:
        return Response({'error': 'No voucher to reverse (nothing was posted).'}, status=400)
    if obj.voucher.is_reversed:
        return Response({'error': 'Already reversed.'}, status=400)
    try:
        reverse_transaction(obj.voucher, user=request.user)
        return Response({'status': 'reversed', 'kind': kind, 'id': pk})
    except ValidationError as e:
        return _err(e)


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

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ageing(request):
    """Pending bill dues bucketed by age. Buckets: 0-7, 8-15, 16-30, 31+.
    Grouped per customer, with column and grand totals."""
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
    return Response({'buckets': buckets, 'rows': rows,
                     'totals': totals, 'grand_total': grand})


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
