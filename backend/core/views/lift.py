"""Best day to lift: the admin's daily market rate + the lift planner report."""
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..lift import NoPrice, lift_plan
from ..models import Flock, MarketRate
from ..permissions import IsAdmin


class MarketRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketRate
        fields = ['id', 'date', 'rate_per_kg', 'notes']
        validators = []

    def validate_date(self, value):
        if value > timezone.localdate():
            raise ValidationError('A market rate cannot be for a future date.')
        return value

    def validate_rate_per_kg(self, value):
        if not (Decimal('20') <= value <= Decimal('500')):
            raise ValidationError('Enter the live-bird rate in ₹ per kg (20–500).')
        return value


class MarketRateViewSet(viewsets.ModelViewSet):
    """Admin only. Saving a rate for a date that already has one corrects it."""
    queryset = MarketRate.objects.all()
    serializer_class = MarketRateSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset()[:60]

    def create(self, request, *args, **kwargs):
        existing = MarketRate.objects.filter(date=request.data.get('date')).first() if request.data.get('date') else None
        if existing is None:
            return super().create(request, *args, **kwargs)
        s = self.get_serializer(existing, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])   # business-sensitive: admin only
def lift_planner(request):
    """?trend=0 keeps today's price flat (default: follow half the recent trend)."""
    trend = request.query_params.get('trend', '1') != '0'
    today = timezone.localdate()
    flocks = Flock.objects.select_related('farm').filter(status='active')
    try:
        return Response(lift_plan(flocks, today, trend=trend))
    except NoPrice as exc:
        return Response({'error': str(exc), 'needs_rate': True}, status=200)
