from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.exceptions import ValidationError

from accounting.models import Party
from inventory.models import Item, Unit
from ..models import (
    LayerFlock, Purchase, FeedBatch, FeedToFlock, Application,
    EggSale, Collection, Payment, Expense,
)
from ..serializers import (
    PurchaseSerializer, FeedBatchSerializer, FeedToFlockSerializer,
    ApplicationSerializer, EggSaleSerializer, CollectionSerializer,
    PaymentSerializer, ExpenseSerializer,
)
from ..services import (
    create_purchase, create_feed_batch, send_feed_to_flock, apply_to_flock,
    create_expense, create_egg_sale, create_collection, create_payment,
    reverse_transaction, set_party_opening, set_cash_opening,
)
from ._helpers import err, today_or


def _party(pk):
    return Party.objects.get(id=pk)


def _item(pk):
    return Item.objects.get(id=pk) if pk else None


def _unit(pk):
    return Unit.objects.get(id=pk) if pk else None


def _flock(pk):
    return LayerFlock.objects.get(id=pk) if pk else None


# ─── PURCHASES ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def purchases(request):
    if request.method == 'GET':
        qs = Purchase.objects.select_related('vendor', 'item', 'flock').all()
        return Response(PurchaseSerializer(qs, many=True).data)
    d = request.data
    try:
        p = create_purchase(
            vendor=_party(d['vendor']), kind=d['kind'],
            date=today_or(d.get('date')), qty=d['qty'], rate=d['rate'],
            item=_item(d.get('item')), unit=_unit(d.get('unit')),
            flock=_flock(d.get('flock')), note=d.get('note', ''), user=request.user,
        )
        return Response(PurchaseSerializer(p).data, status=201)
    except ValidationError as e:
        return err(e)


# ─── FEED BATCH (production) ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def feed_batches(request):
    if request.method == 'GET':
        qs = FeedBatch.objects.select_related('feed_item').prefetch_related('inputs').all()
        return Response(FeedBatchSerializer(qs, many=True).data)
    d = request.data
    try:
        inputs = [{'item': _item(i['item']), 'qty_kg': i['qty_kg'], 'cost': i['cost']}
                  for i in d.get('inputs', [])]
        b = create_feed_batch(
            date=today_or(d.get('date')), feed_item=_item(d['feed_item']),
            output_kg=d['output_kg'], inputs=inputs,
            overhead=d.get('overhead', 0), note=d.get('note', ''), user=request.user,
        )
        return Response(FeedBatchSerializer(b).data, status=201)
    except ValidationError as e:
        return err(e)


# ─── FEED -> FLOCK ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def feed_to_flock(request):
    if request.method == 'GET':
        qs = FeedToFlock.objects.select_related('flock', 'feed_item').all()
        return Response(FeedToFlockSerializer(qs, many=True).data)
    d = request.data
    try:
        f = send_feed_to_flock(
            flock=_flock(d['flock']), feed_item=_item(d['feed_item']),
            date=today_or(d.get('date')), qty_kg=d['qty_kg'],
            cost_per_kg=d.get('cost_per_kg'), note=d.get('note', ''), user=request.user,
        )
        return Response(FeedToFlockSerializer(f).data, status=201)
    except ValidationError as e:
        return err(e)


# ─── APPLY medicine/vaccine/premix ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def applications(request):
    if request.method == 'GET':
        qs = Application.objects.select_related('flock', 'item').all()
        return Response(ApplicationSerializer(qs, many=True).data)
    d = request.data
    try:
        a = apply_to_flock(
            flock=_flock(d['flock']), kind=d['kind'], date=today_or(d.get('date')),
            amount=d['amount'], item=_item(d.get('item')), qty=d.get('qty', 0),
            note=d.get('note', ''), user=request.user,
        )
        return Response(ApplicationSerializer(a).data, status=201)
    except ValidationError as e:
        return err(e)


# ─── EGG SALE ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def egg_sales(request):
    if request.method == 'GET':
        qs = EggSale.objects.select_related('party', 'flock').all()
        party = request.query_params.get('party')
        flock = request.query_params.get('flock')
        if party:
            qs = qs.filter(party_id=party)
        if flock:
            qs = qs.filter(flock_id=flock)
        return Response(EggSaleSerializer(qs, many=True).data)
    d = request.data
    try:
        s = create_egg_sale(
            party=_party(d['party']), flock=_flock(d['flock']),
            date=today_or(d.get('date')), trays=d['trays'],
            rate_per_tray=d['rate_per_tray'], note=d.get('note', ''), user=request.user,
        )
        return Response(EggSaleSerializer(s).data, status=201)
    except ValidationError as e:
        return err(e)


# ─── COLLECTION / PAYMENT / EXPENSE ───

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def collections(request):
    if request.method == 'GET':
        qs = Collection.objects.select_related('party').all()
        return Response(CollectionSerializer(qs, many=True).data)
    d = request.data
    try:
        c = create_collection(
            party=_party(d['party']), date=today_or(d.get('date')),
            amount=d['amount'], mode=d.get('mode', 'CASH'),
            note=d.get('note', ''), user=request.user,
        )
        return Response(CollectionSerializer(c).data, status=201)
    except ValidationError as e:
        return err(e)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def payments(request):
    if request.method == 'GET':
        qs = Payment.objects.select_related('party').all()
        return Response(PaymentSerializer(qs, many=True).data)
    d = request.data
    try:
        p = create_payment(
            party=_party(d['party']), date=today_or(d.get('date')),
            amount=d['amount'], mode=d.get('mode', 'CASH'),
            note=d.get('note', ''), user=request.user,
        )
        return Response(PaymentSerializer(p).data, status=201)
    except ValidationError as e:
        return err(e)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def expenses(request):
    if request.method == 'GET':
        qs = Expense.objects.all()
        return Response(ExpenseSerializer(qs, many=True).data)
    d = request.data
    try:
        e = create_expense(
            date=today_or(d.get('date')), account_code=d['account_code'],
            amount=d['amount'], mode=d.get('mode', 'CASH'),
            split_across_flocks=d.get('split_across_flocks', True),
            flock=_flock(d.get('flock')), note=d.get('note', ''), user=request.user,
        )
        return Response(ExpenseSerializer(e).data, status=201)
    except ValidationError as ex:
        return err(ex)


# ─── REVERSE ───

_MODEL_MAP = {
    'purchase': Purchase, 'feed-batch': FeedBatch, 'feed-to-flock': FeedToFlock,
    'application': Application, 'egg-sale': EggSale, 'collection': Collection,
    'payment': Payment, 'expense': Expense,
}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reverse_entry(request, kind, pk):
    model = _MODEL_MAP.get(kind)
    if not model:
        return Response({'error': f'Unknown type: {kind}'}, status=400)
    try:
        obj = model.objects.select_related('voucher').get(pk=pk)
    except model.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)
    if not obj.voucher:
        return Response({'error': 'No voucher to reverse.'}, status=400)
    if obj.voucher.is_reversed:
        return Response({'error': 'Already reversed.'}, status=400)
    try:
        reverse_transaction(obj.voucher, user=request.user)
        return Response({'status': 'reversed', 'kind': kind, 'id': pk})
    except ValidationError as e:
        return err(e)


# ─── OPENING BALANCES ───

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def opening_party(request):
    d = request.data
    try:
        set_party_opening(party=_party(d['party']), amount=d['amount'],
                          as_of=today_or(d.get('as_of')), user=request.user)
        return Response({'status': 'ok'}, status=201)
    except ValidationError as e:
        return err(e)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def opening_cash(request):
    d = request.data
    try:
        set_cash_opening(account_code=d['account_code'], amount=d['amount'],
                        as_of=today_or(d.get('as_of')), user=request.user)
        return Response({'status': 'ok'}, status=201)
    except ValidationError as e:
        return err(e)
