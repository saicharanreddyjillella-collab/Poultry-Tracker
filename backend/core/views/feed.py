from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Q

from ..models import Farm, DailyEntry, FeedOrder, FeedTransfer
from ..serializers import FeedOrderSerializer, FeedTransferSerializer


class FeedOrderViewSet(viewsets.ModelViewSet):
    queryset = FeedOrder.objects.select_related('farm', 'ordered_by').all()
    serializer_class = FeedOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        farm_id = self.request.query_params.get('farm')
        status_filter = self.request.query_params.get('status')
        if farm_id:
            qs = qs.filter(farm_id=farm_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        serializer.save(ordered_by=self.request.user)


@api_view(['POST'])
def mark_order_sent(request, order_id):
    from django.utils import timezone
    profile = getattr(request.user, 'profile', None)
    if not profile or (not profile.is_plant and not profile.is_admin):
        return Response({'error': 'Only plant users can mark orders as sent'}, status=403)
    try:
        order = FeedOrder.objects.get(id=order_id)
    except FeedOrder.DoesNotExist:
        return Response({'error': 'Order not found'}, status=404)
    if order.status != 'pending':
        return Response({'error': f'Order is already {order.status}'}, status=400)
    order.status = 'sent'
    order.sent_date = timezone.now()
    order.save()
    return Response(FeedOrderSerializer(order).data)


@api_view(['POST'])
def mark_order_delivered(request, order_id):
    from django.utils import timezone
    try:
        order = FeedOrder.objects.get(id=order_id)
    except FeedOrder.DoesNotExist:
        return Response({'error': 'Order not found'}, status=404)
    if order.status != 'sent':
        return Response({'error': f'Order must be "sent", currently: {order.status}'}, status=400)
    if not request.user.profile.is_admin and not request.user.profile.can_edit_farm(order.farm):
        return Response({'error': 'Permission denied'}, status=403)
    order.status = 'delivered'
    order.delivered_date = timezone.now()
    order.save()
    return Response(FeedOrderSerializer(order).data)


@api_view(['POST'])
def cancel_order(request, order_id):
    try:
        order = FeedOrder.objects.get(id=order_id)
    except FeedOrder.DoesNotExist:
        return Response({'error': 'Order not found'}, status=404)
    if order.status not in ('pending', 'sent'):
        return Response({'error': f'Cannot cancel: {order.status}'}, status=400)
    if not request.user.profile.is_admin and not request.user.profile.can_edit_farm(order.farm):
        return Response({'error': 'Permission denied'}, status=403)
    order.status = 'cancelled'
    order.save()
    return Response(FeedOrderSerializer(order).data)


@api_view(['GET'])
def feed_stock(request):
    farm_id = request.query_params.get('farm')
    farms_qs = Farm.objects.all()
    if farm_id:
        farms_qs = farms_qs.filter(id=farm_id)

    result = []
    for farm in farms_qs:
        delivered = FeedOrder.objects.filter(farm=farm, status='delivered').values('feed_type').annotate(total=Sum('quantity_bags'))
        delivered_map = {d['feed_type']: float(d['total']) for d in delivered}

        consumed = DailyEntry.objects.filter(flock__farm=farm).aggregate(
            bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'),
        )
        consumed_bpsc = float(consumed['bpsc'] or 0)
        consumed_bsc = float(consumed['bsc'] or 0)
        consumed_bfp = float(consumed['bfp'] or 0)

        pending = FeedOrder.objects.filter(farm=farm, status__in=['pending', 'sent']).values('feed_type').annotate(total=Sum('quantity_bags'))
        pending_map = {p['feed_type']: float(p['total']) for p in pending}

        transfers_in = FeedTransfer.objects.filter(to_farm=farm).values('feed_type').annotate(total=Sum('quantity_bags'))
        in_map = {t['feed_type']: float(t['total']) for t in transfers_in}

        transfers_out = FeedTransfer.objects.filter(from_farm=farm).values('feed_type').annotate(total=Sum('quantity_bags'))
        out_map = {t['feed_type']: float(t['total']) for t in transfers_out}

        stock_bpsc = delivered_map.get('BPSC', 0) + in_map.get('BPSC', 0) - out_map.get('BPSC', 0) - consumed_bpsc
        stock_bsc = delivered_map.get('BSC', 0) + in_map.get('BSC', 0) - out_map.get('BSC', 0) - consumed_bsc
        stock_bfp = delivered_map.get('BFP', 0) + in_map.get('BFP', 0) - out_map.get('BFP', 0) - consumed_bfp

        result.append({
            'farm_id': farm.id, 'farm_code': farm.farm_code, 'farm_name': farm.name,
            'stock': {
                'bpsc': round(stock_bpsc, 1), 'bsc': round(stock_bsc, 1),
                'bfp': round(stock_bfp, 1), 'total': round(stock_bpsc + stock_bsc + stock_bfp, 1),
            },
            'delivered': {'bpsc': delivered_map.get('BPSC', 0), 'bsc': delivered_map.get('BSC', 0), 'bfp': delivered_map.get('BFP', 0)},
            'consumed': {'bpsc': consumed_bpsc, 'bsc': consumed_bsc, 'bfp': consumed_bfp},
            'pending_orders': {'bpsc': pending_map.get('BPSC', 0), 'bsc': pending_map.get('BSC', 0), 'bfp': pending_map.get('BFP', 0)},
        })

    return Response(result)


class FeedTransferViewSet(viewsets.ModelViewSet):
    queryset = FeedTransfer.objects.select_related('from_farm', 'to_farm', 'transferred_by').all()
    serializer_class = FeedTransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        farm_id = self.request.query_params.get('farm')
        if farm_id:
            qs = qs.filter(Q(from_farm_id=farm_id) | Q(to_farm_id=farm_id))
        return qs

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        from_farm = serializer.validated_data['from_farm']
        to_farm = serializer.validated_data['to_farm']
        if from_farm.id == to_farm.id:
            raise ValidationError({'to_farm': 'Cannot transfer to the same farm.'})
        serializer.save(transferred_by=self.request.user)
