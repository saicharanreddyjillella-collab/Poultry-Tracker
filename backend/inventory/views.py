from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Unit, Item, StockMovement, StockGroup
from .serializers import (
    UnitSerializer, ItemSerializer, StockMovementSerializer, StockGroupSerializer,
)


class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticated]


class StockGroupViewSet(viewsets.ModelViewSet):
    queryset = StockGroup.objects.select_related('under').all()
    serializer_class = StockGroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        biz = self.request.query_params.get('business')
        if biz:
            # Ensure the business has a Primary group, then return its groups.
            StockGroup.primary_for(biz)
            qs = qs.filter(business=biz)
        return qs

    def perform_create(self, serializer):
        biz = serializer.validated_data.get('business', 'layer')
        # New groups nest under Primary by default if no parent given.
        if not serializer.validated_data.get('under'):
            serializer.save(under=StockGroup.primary_for(biz))
        else:
            serializer.save()


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.select_related('base_unit', 'stock_group').all()
    serializer_class = ItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        biz = self.request.query_params.get('business')
        kind = self.request.query_params.get('kind')
        group = self.request.query_params.get('stock_group')
        if biz:
            qs = qs.filter(business=biz)
        if kind:
            qs = qs.filter(kind=kind)
        if group:
            qs = qs.filter(stock_group_id=group)
        return qs

    def perform_create(self, serializer):
        biz = serializer.validated_data.get('business', 'layer')
        if not serializer.validated_data.get('stock_group'):
            serializer.save(stock_group=StockGroup.primary_for(biz))
        else:
            serializer.save()


class StockMovementViewSet(viewsets.ReadOnlyModelViewSet):
    """Movements are created via business-module actions, not edited directly."""
    queryset = StockMovement.objects.select_related('item', 'entered_unit').all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        item = self.request.query_params.get('item')
        biz = self.request.query_params.get('business')
        if item:
            qs = qs.filter(item_id=item)
        if biz:
            qs = qs.filter(business=biz)
        return qs


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def stock_on_hand_view(request):
    """Current stock for every item (optionally filtered by business)."""
    biz = request.query_params.get('business')
    qs = Item.objects.select_related('base_unit').filter(active=True)
    if biz:
        qs = qs.filter(business=biz)
    rows = [{
        'item_id': it.id, 'name': it.name, 'kind': it.kind,
        'unit': it.base_unit.symbol,
        'stock': it.stock_on_hand(business=biz),
    } for it in qs]
    return Response({'rows': rows})
