import logging

from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import Flock, BillConfig, Bill, BillVersion
from ..serializers import BillConfigSerializer, BillSerializer, BillVersionSerializer

logger = logging.getLogger(__name__)

REOPEN_REASON_MIN_CHARS = 10


@api_view(['GET', 'PUT'])
def bill_config_view(request):
    config = BillConfig.get_active()
    if request.method == 'GET':
        return Response(BillConfigSerializer(config).data)
    if not request.user.profile.is_admin:
        return Response({'error': 'Admin only'}, status=403)
    serializer = BillConfigSerializer(config, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=400)


@api_view(['POST'])
def close_flock_and_generate_bill(request, flock_id):
    from ..billing import generate_bill
    try:
        flock = Flock.objects.select_related('farm').get(id=flock_id)
    except Flock.DoesNotExist:
        return Response({'error': 'Flock not found'}, status=404)

    if flock.status == 'closed':
        if hasattr(flock, 'bill'):
            return Response(BillSerializer(flock.bill).data)
        bill = generate_bill(flock, request.user)
        return Response(BillSerializer(bill).data)

    if not request.user.profile.can_edit_farm(flock.farm):
        return Response({'error': 'Permission denied'}, status=403)

    # Apply recovery flags from request to farm before billing
    farm = flock.farm
    flag_fields = [
        'recovery_excess_mortality', 'recovery_negligence', 'recovery_shortage',
        'recovery_fcr', 'recovery_ifft', 'medicine_use_actual',
        'fcr_benchmark_enabled',
    ]
    for field in flag_fields:
        if field in request.data:
            setattr(farm, field, request.data[field])
    farm.save()

    # Close flock
    flock.status = 'closed'
    flock.save()

    # Generate bill
    bill = generate_bill(flock, request.user)
    return Response(BillSerializer(bill).data, status=201)


@api_view(['GET'])
def get_bill(request, flock_id):
    try:
        bill = Bill.objects.select_related('flock', 'flock__farm').get(flock_id=flock_id)
    except Bill.DoesNotExist:
        return Response({'error': 'Bill not found'}, status=404)
    return Response(BillSerializer(bill).data)


@api_view(['GET'])
def list_bills(request):
    bills = Bill.objects.select_related('flock', 'flock__farm').all()
    return Response(BillSerializer(bills, many=True).data)


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
    if not Flock.objects.filter(id=flock_id).exists():
        return Response({'error': 'Flock not found'}, status=404)
    versions = BillVersion.objects.filter(flock_id=flock_id).select_related('reopened_by')
    current = Bill.objects.filter(flock_id=flock_id).values('version', 'net_payable', 'generated_at').first()
    return Response({
        'flock_id': flock_id,
        'current': current,
        'versions': BillVersionSerializer(versions, many=True).data,
    })
