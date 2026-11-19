from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum, Q

from ..models import Farm, DailyEntry, FeedOrder, FeedTransfer
from ..serializers import FeedOrderSerializer, FeedTransferSerializer
from ..access import is_admin, is_plant, visible_farm_ids
from rest_framework.exceptions import PermissionDenied, ValidationError


def _can_manage_farm(user, farm):
    """Admin, or the supervisor responsible for this farm. Never the feed mill."""
    if is_admin(user):
        return True
    if is_plant(user):
        return False
    return user.profile.can_edit_farm(farm)


class FeedOrderViewSet(viewsets.ModelViewSet):
    queryset = FeedOrder.objects.select_related('farm', 'ordered_by', 'flock').all()
    serializer_class = FeedOrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset().filter(farm_id__in=visible_farm_ids(self.request.user))
        farm_id = self.request.query_params.get('farm')
        status_filter = self.request.query_params.get('status')
        if farm_id:
            qs = qs.filter(farm_id=farm_id)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        farm = serializer.validated_data['farm']
        flock = serializer.validated_data.get('flock')
        if not _can_manage_farm(self.request.user, farm):
            raise PermissionDenied('You can only order feed for farms in your regions.')
        if flock is not None and flock.farm_id != farm.id:
            raise ValidationError({'flock': 'That flock is not on this farm.'})
        serializer.save(ordered_by=self.request.user)

    def _check_editable(self, order):
        # The mill moves orders along with mark-sent; editing/deleting an order is
        # for its farm's supervisor (or admin), and only before it's dispatched.
        if not _can_manage_farm(self.request.user, order.farm):
            raise PermissionDenied('You can only change feed orders for farms in your regions.')
        if order.status != 'pending' and not is_admin(self.request.user):
            raise PermissionDenied(f'This order is already {order.status} and can no longer be changed.')

    def perform_update(self, serializer):
        self._check_editable(serializer.instance)
        farm = serializer.validated_data.get('farm', serializer.instance.farm)
        if not _can_manage_farm(self.request.user, farm):
            raise PermissionDenied('You can only order feed for farms in your regions.')
        serializer.save()

    def perform_destroy(self, instance):
        self._check_editable(instance)
        instance.delete()


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
    farms_qs = Farm.objects.filter(id__in=visible_farm_ids(request.user))
    if farm_id:
        farms_qs = farms_qs.filter(id=farm_id)

    # Page speed: every total for all farms in five grouped queries (not five per farm).
    farms = list(farms_qs)
    ids = [f.id for f in farms]

    def by_farm(qs, key):
        out = {}
        for r in qs.values(key, 'feed_type').annotate(total=Sum('quantity_bags')):
            out.setdefault(r[key], {})[r['feed_type']] = float(r['total'])
        return out
    delivered_all = by_farm(FeedOrder.objects.filter(farm_id__in=ids, status='delivered'), 'farm_id')
    pending_all = by_farm(FeedOrder.objects.filter(farm_id__in=ids, status__in=['pending', 'sent']), 'farm_id')
    in_all = by_farm(FeedTransfer.objects.filter(to_farm_id__in=ids), 'to_farm_id')
    out_all = by_farm(FeedTransfer.objects.filter(from_farm_id__in=ids), 'from_farm_id')
    consumed_all = {r['flock__farm_id']: r for r in DailyEntry.objects.filter(flock__farm_id__in=ids)
                    .values('flock__farm_id').annotate(bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'),
                                                       bfp=Sum('feed_bfp_bags'))}

    result = []
    for farm in farms:
        delivered_map = delivered_all.get(farm.id, {})
        consumed = consumed_all.get(farm.id, {})
        consumed_bpsc = float(consumed.get('bpsc') or 0)
        consumed_bsc = float(consumed.get('bsc') or 0)
        consumed_bfp = float(consumed.get('bfp') or 0)
        pending_map = pending_all.get(farm.id, {})
        in_map = in_all.get(farm.id, {})
        out_map = out_all.get(farm.id, {})

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
        ids = visible_farm_ids(self.request.user)
        qs = super().get_queryset().filter(Q(from_farm_id__in=ids) | Q(to_farm_id__in=ids))
        farm_id = self.request.query_params.get('farm')
        if farm_id:
            qs = qs.filter(Q(from_farm_id=farm_id) | Q(to_farm_id=farm_id))
        return qs

    def _check_both_farms(self, from_farm, to_farm):
        user = self.request.user
        if not (_can_manage_farm(user, from_farm) and _can_manage_farm(user, to_farm)):
            raise PermissionDenied('You can only transfer feed between farms in your regions.')

    def perform_update(self, serializer):
        inst = serializer.instance
        self._check_both_farms(inst.from_farm, inst.to_farm)
        self._check_both_farms(serializer.validated_data.get('from_farm', inst.from_farm),
                               serializer.validated_data.get('to_farm', inst.to_farm))
        serializer.save()

    def perform_destroy(self, instance):
        self._check_both_farms(instance.from_farm, instance.to_farm)
        instance.delete()

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        from_farm = serializer.validated_data['from_farm']
        to_farm = serializer.validated_data['to_farm']
        self._check_both_farms(from_farm, to_farm)
        for side, farm, flock in (('from_flock', from_farm, serializer.validated_data.get('from_flock')),
                                  ('to_flock', to_farm, serializer.validated_data.get('to_flock'))):
            if flock is not None and flock.farm_id != farm.id:
                raise ValidationError({side: 'That flock is not on the chosen farm.'})
        if from_farm.id == to_farm.id:
            raise ValidationError({'to_farm': 'Cannot transfer to the same farm.'})
        serializer.save(transferred_by=self.request.user)
