from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..models import Flock, BillConfig, Bill
from ..serializers import BillConfigSerializer, BillSerializer


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

    flock.status = 'closed'
    flock.save()
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
