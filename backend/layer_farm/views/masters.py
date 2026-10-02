from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import LayerFarm, LayerFlock, FlockCost, DailyEntry
from ..serializers import (
    LayerFarmSerializer, LayerFlockSerializer, FlockCostSerializer,
    DailyEntrySerializer,
)


class FarmViewSet(viewsets.ModelViewSet):
    queryset = LayerFarm.objects.all()
    serializer_class = LayerFarmSerializer
    permission_classes = [IsAuthenticated]


class FlockViewSet(viewsets.ModelViewSet):
    queryset = LayerFlock.objects.select_related('farm').all()
    serializer_class = LayerFlockSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        farm = self.request.query_params.get('farm')
        status = self.request.query_params.get('status')
        if farm:
            qs = qs.filter(farm_id=farm)
        if status:
            qs = qs.filter(status=status)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class DailyEntryViewSet(viewsets.ModelViewSet):
    queryset = DailyEntry.objects.select_related('flock').all()
    serializer_class = DailyEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        flock = self.request.query_params.get('flock')
        if flock:
            qs = qs.filter(flock_id=flock)
        return qs

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        flock = serializer.validated_data['flock']
        mort = serializer.validated_data.get('mortality', 0) or 0
        culls = serializer.validated_data.get('culls', 0) or 0
        if mort + culls > flock.live_birds:
            raise ValidationError({
                'mortality': f'Mortality + culls ({mort + culls}) cannot exceed '
                             f'live birds ({flock.live_birds}).'})
        serializer.save(created_by=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def flock_costs(request, flock_id):
    """All cost lines charged to a flock, newest first."""
    rows = FlockCost.objects.filter(flock_id=flock_id).order_by('-date', '-id')
    return Response(FlockCostSerializer(rows, many=True).data)
