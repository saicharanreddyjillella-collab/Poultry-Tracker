import logging

from django.db import transaction
from django.db.models import F
from rest_framework.exceptions import ValidationError
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import Flock, BillConfig, Bill, BillVersion
from ..serializers import BillConfigSerializer, BillSerializer, BillVersionSerializer
from ..access import is_admin, deny_plant, get_visible_flock, visible_farm_ids

logger = logging.getLogger(__name__)

REOPEN_REASON_MIN_CHARS = 10


@api_view(['GET', 'PUT'])
def bill_config_view(request):
    # Billing settings (costs, rates, TDS) are admin-only, read and write.
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    config = BillConfig.get_active()
    if request.method == 'GET':
        return Response(BillConfigSerializer(config).data)
    serializer = BillConfigSerializer(config, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


RATE_CARD_COPY_SKIP = {'id', 'is_active', 'created_at', 'updated_at', 'name', 'effective_from', 'notes'}


def _card_data(card):
    data = BillConfigSerializer(card).data
    data['label'] = card.label
    data['bills_count'] = card.bills.count()
    return data


@api_view(['GET', 'POST'])
def rate_cards(request):
    """Billing rate cards (admin). POST creates one, copying every rate from `copy_from`
    (default: the newest card) and then applying the fields sent."""
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    if request.method == 'GET':
        BillConfig.get_active()                                   # always at least one card
        cards = BillConfig.objects.order_by(F('effective_from').desc(nulls_last=True), '-id')
        return Response([_card_data(c) for c in cards])
    src_id = request.data.get('copy_from')
    src = (BillConfig.objects.filter(pk=src_id).first() if src_id
           else BillConfig.objects.order_by(F('effective_from').desc(nulls_last=True), '-id').first())
    base = {}
    if src:
        base = {f.name: getattr(src, f.name) for f in BillConfig._meta.concrete_fields if f.name not in RATE_CARD_COPY_SKIP}
    data = {k: v for k, v in request.data.items() if k not in ('copy_from', 'is_active', 'id')}
    ser = BillConfigSerializer(data={**{k: (str(v) if v is not None else None) for k, v in base.items()}, **data})
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    with transaction.atomic():
        card = ser.save(is_active=not BillConfig.objects.exists())
    return Response(_card_data(card), status=201)


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def rate_card_detail(request, card_id):
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    card = BillConfig.objects.filter(pk=card_id).first()
    if card is None:
        return Response({'error': 'Rate card not found'}, status=404)
    if request.method == 'GET':
        return Response(_card_data(card))
    if request.method == 'DELETE':
        if card.is_active:
            return Response({'error': 'This is the default card. Make another card the default first.'}, status=400)
        if card.bills.exists():
            return Response({'error': f'{card.label} was used for {card.bills.count()} bill(s) and is kept for the record.'},
                            status=400)
        card.delete()
        return Response(status=204)
    data = {k: v for k, v in request.data.items() if k not in ('is_active', 'id')}
    ser = BillConfigSerializer(card, data=data, partial=True)
    if not ser.is_valid():
        return Response(ser.errors, status=400)
    ser.save()
    return Response(_card_data(card))


@api_view(['POST'])
def rate_card_make_default(request, card_id):
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    card = BillConfig.objects.filter(pk=card_id).first()
    if card is None:
        return Response({'error': 'Rate card not found'}, status=404)
    with transaction.atomic():
        for other in BillConfig.objects.filter(is_active=True).exclude(pk=card.pk):
            other.is_active = False
            other.save(update_fields=['is_active', 'updated_at'])     # save() so the change is audited
        card.is_active = True
        card.save(update_fields=['is_active', 'updated_at'])
    return Response(_card_data(card))


FARM_BILL_FLAGS = [
    'recovery_excess_mortality', 'recovery_negligence', 'recovery_shortage',
    'recovery_fcr', 'recovery_ifft', 'medicine_use_actual', 'fcr_benchmark_enabled',
]


def _chosen_card(request, flock):
    """Admins may pick a card; everyone else gets the card in effect on the placement date."""
    card_id = request.data.get('rate_card')
    if card_id and is_admin(request.user):
        card = BillConfig.objects.filter(pk=card_id).first()
        if card is None:
            raise ValidationError({'rate_card': 'Rate card not found'})
        return card
    return BillConfig.for_date(flock.placement_date)


class _Preview(Exception):
    pass


@api_view(['POST'])
def bill_preview(request, flock_id):
    """What the bill would come to with a given card and recovery choices. Nothing is saved."""
    from ..billing import generate_bill
    if not is_admin(request.user):
        return Response({'error': 'Admin only'}, status=403)
    flock = get_visible_flock(request.user, flock_id)
    if hasattr(flock, 'bill'):
        return Response({'error': 'This flock already has a bill.'}, status=400)
    card = _chosen_card(request, flock)
    suggested = BillConfig.for_date(flock.placement_date)
    farm = flock.farm
    for field in FARM_BILL_FLAGS:
        if field in request.data:
            setattr(farm, field, bool(request.data[field]))      # in memory only
    result = {}
    try:
        with transaction.atomic():
            bill = generate_bill(flock, request.user, config=card)
            result = BillSerializer(bill).data
            raise _Preview
    except _Preview:
        pass
    keep = ('growing_charges_per_kg', 'growing_charges_total', 'rate_incentive_per_kg', 'rate_incentive_total',
            'production_cost_per_kg', 'farmer_grade', 'total_recoveries', 'gross_payable', 'net_payable',
            'tds_amount', 'amount_paid', 'total_sold_weight_kg', 'avg_selling_price', 'fcr_benchmark_adjustment')
    return Response({
        'rate_card': card.pk, 'rate_card_name': card.label, 'growing_method': card.growing_method,
        'suggested_card': suggested.pk, 'suggested_card_name': suggested.label,
        **{k: result.get(k) for k in keep},
    })


@api_view(['POST'])
def close_flock_and_generate_bill(request, flock_id):
    from ..billing import generate_bill
    deny_plant(request.user)
    flock = get_visible_flock(request.user, flock_id)             # 404 other region / missing
    if not is_admin(request.user) and not request.user.profile.can_edit_farm(flock.farm):
        return Response({'error': 'Permission denied'}, status=403)

    if flock.status == 'closed':
        if hasattr(flock, 'bill'):
            return Response(BillSerializer(flock.bill).data)
        bill = generate_bill(flock, request.user, config=_chosen_card(request, flock))
        return Response(BillSerializer(bill).data)

    if not request.user.profile.can_edit_farm(flock.farm):
        return Response({'error': 'Permission denied'}, status=403)

    # Apply recovery flags from request to farm before billing
    farm = flock.farm
    card = _chosen_card(request, flock)
    for field in FARM_BILL_FLAGS:
        if field in request.data:
            setattr(farm, field, request.data[field])
    farm.save()

    # Close flock
    flock.status = 'closed'
    flock.save()

    # Generate bill
    bill = generate_bill(flock, request.user, config=card)
    return Response(BillSerializer(bill).data, status=201)


@api_view(['GET'])
def get_bill(request, flock_id):
    deny_plant(request.user)
    try:
        bill = Bill.objects.select_related('flock', 'flock__farm').get(
            flock_id=flock_id, flock__farm_id__in=visible_farm_ids(request.user))
    except Bill.DoesNotExist:
        return Response({'error': 'Bill not found'}, status=404)
    return Response(BillSerializer(bill).data)


@api_view(['GET'])
def list_bills(request):
    """?approval=pending|approved  ?payment=unpaid|part|paid"""
    deny_plant(request.user)
    bills = (Bill.objects.select_related('flock', 'flock__farm', 'approved_by', 'generated_by')
             .prefetch_related('flock__payments__recorded_by')
             .filter(flock__farm_id__in=visible_farm_ids(request.user)))
    if request.query_params.get('approval'):
        bills = bills.filter(approval_status=request.query_params['approval'])
    rows = BillSerializer(bills, many=True).data
    if request.query_params.get('payment'):
        rows = [r for r in rows if r['payment_status'] == request.query_params['payment']]
    return Response(rows)


def _admin_bill(request, flock_id):
    if not is_admin(request.user):
        return None, Response({'error': 'Only an admin can do this.'}, status=403)
    bill = Bill.objects.select_related('flock', 'flock__farm').filter(flock_id=flock_id).first()
    if bill is None:
        return None, Response({'error': 'This flock has no bill.'}, status=404)
    return bill, None


@api_view(['POST'])
def approve_bill(request, flock_id):
    """Admin approves a supervisor's bill. Payments can be recorded after this."""
    from django.utils import timezone
    from ..billlock import unlocked
    bill, err = _admin_bill(request, flock_id)
    if err:
        return err
    if bill.approval_status == 'approved':
        return Response({'error': 'This bill is already approved.'}, status=400)
    with unlocked():
        bill.approval_status, bill.approved_by, bill.approved_at = 'approved', request.user, timezone.now()
        bill.approval_note = (request.data.get('note') or '').strip()
        bill.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'approval_note'])
    return Response(BillSerializer(bill).data)


@api_view(['POST'])
def add_bill_payment(request, flock_id):
    """Admin records a payment to the grower: {date, amount, mode, reference, notes}."""
    from ..models import BillPayment
    from ..serializers import BillPaymentSerializer
    bill, err = _admin_bill(request, flock_id)
    if err:
        return err
    if bill.approval_status != 'approved':
        return Response({'error': 'Approve the bill before recording payments.'}, status=400)
    ser = BillPaymentSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    amount = ser.validated_data['amount']
    if amount <= 0:
        return Response({'amount': ['Enter an amount above ₹0.']}, status=400)
    if amount > bill.balance_due:
        return Response({'amount': [f'Only ₹{bill.balance_due:,} is still due on this bill.']}, status=400)
    from django.utils import timezone
    if ser.validated_data['date'] < timezone.localdate(bill.generated_at):      # Indian date, not UTC
        return Response({'date': ['A payment cannot be dated before the bill.']}, status=400)
    ser.save(flock=bill.flock, bill_version=bill.version, recorded_by=request.user)
    bill.flock.refresh_from_db()
    return Response(BillSerializer(Bill.objects.get(pk=bill.pk)).data, status=201)


@api_view(['DELETE'])
def delete_bill_payment(request, payment_id):
    """Admin removes a payment recorded by mistake (kept in the change history)."""
    from ..models import BillPayment
    if not is_admin(request.user):
        return Response({'error': 'Only an admin can do this.'}, status=403)
    p = BillPayment.objects.filter(pk=payment_id).first()
    if p is None:
        return Response({'error': 'Not found'}, status=404)
    flock_id = p.flock_id
    p.delete()
    bill = Bill.objects.filter(flock_id=flock_id).first()
    return Response(BillSerializer(bill).data if bill else {}, status=200)


@api_view(['POST'])
def reopen_bill(request, flock_id):
    """E5: admin-only. Archive the current bill as a BillVersion, delete the
    live bill and set the flock back to active so its data can be corrected.
    Closing the flock again generates the next bill version."""
    from ..audit import snapshot
    from ..billlock import unlocked

    if not request.user.profile.is_admin:
        return Response({'error': 'Only an admin can reopen a bill.'}, status=403)
    reason = (request.data.get('reason') or '').strip()
    if len(reason) < REOPEN_REASON_MIN_CHARS:
        return Response(
            {'error': f'A reason of at least {REOPEN_REASON_MIN_CHARS} characters is required to reopen a bill.'},
            status=400)

    with transaction.atomic():
        try:
            bill = Bill.objects.select_for_update().select_related('flock').get(flock_id=flock_id)
        except Bill.DoesNotExist:
            return Response({'error': 'This flock has no generated bill to reopen.'}, status=404)
        flock = bill.flock
        with unlocked():
            archived = BillVersion.objects.create(
                flock=flock, version=bill.version, data=snapshot(bill),
                net_payable=bill.net_payable, amount_paid=bill.amount_paid,
                generated_at=bill.generated_at, reopened_by=request.user, reason=reason,
            )
            bill.delete()
            flock.status = 'active'
            flock.save()

    logger.warning('Bill reopened: flock=%s version=%s by=%s reason=%r',
                   flock.id, archived.version, request.user.username, reason)
    return Response({
        'flock_id': flock.id,
        'status': flock.status,
        'archived': BillVersionSerializer(archived).data,
        'next_version': archived.version + 1,
    })


@api_view(['GET'])
def bill_history(request, flock_id):
    """E5: every archived (superseded) version of a flock's bill, oldest first,
    plus the live bill's version if one exists."""
    deny_plant(request.user)
    get_visible_flock(request.user, flock_id)                     # 404 other region / missing
    versions = BillVersion.objects.filter(flock_id=flock_id).select_related('reopened_by')
    current = Bill.objects.filter(flock_id=flock_id).values('version', 'net_payable', 'generated_at').first()
    return Response({
        'flock_id': flock_id,
        'current': current,
        'versions': BillVersionSerializer(versions, many=True).data,
    })
