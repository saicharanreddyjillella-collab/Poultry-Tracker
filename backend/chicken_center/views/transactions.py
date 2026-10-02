from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from datetime import date as date_cls

from accounting.models import Party
from inventory.models import Item
from ..models import Sale, Purchase, Collection, Payment, Expense, Shrinkage
from ..serializers import (
    SaleSerializer, PurchaseSerializer, CollectionSerializer,
    PaymentSerializer, ExpenseSerializer, ShrinkageSerializer,
)
from ..services import (
    create_sale, create_sale_multi, create_purchase, create_collection, create_payment,
    create_expense, create_shrinkage, reverse_transaction,
    set_party_opening, set_cash_opening,
)
from ._helpers import err as _err


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
        # Multi-item if a non-empty 'lines' array is sent; else single-item.
        lines = d.get('lines')
        if lines:
            sale = create_sale_multi(
                party=Party.objects.get(id=d['party']),
                date=d.get('date') or date_cls.today(),
                lines=[{
                    'item': Item.objects.get(id=ln['item']),
                    'weight_kg': ln['weight_kg'], 'rate_per_kg': ln['rate_per_kg'],
                } for ln in lines],
                note=d.get('note', ''), user=request.user,
            )
        else:
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


# ─── OPENING BALANCES ───

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def opening_party(request):
    d = request.data
    try:
        set_party_opening(
            party=Party.objects.get(id=d['party']),
            amount=d['amount'],
            as_of=d.get('as_of') or date_cls.today(),
            user=request.user,
        )
        return Response({'status': 'ok'}, status=201)
    except ValidationError as e:
        return _err(e)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def opening_cash(request):
    d = request.data
    try:
        set_cash_opening(
            account_code=d['account_code'],
            amount=d['amount'],
            as_of=d.get('as_of') or date_cls.today(),
            user=request.user,
        )
        return Response({'status': 'ok'}, status=201)
    except ValidationError as e:
        return _err(e)

