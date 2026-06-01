from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Sum, F
from datetime import date
from decimal import Decimal
from .models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication
from .serializers import (
    FarmSerializer, FlockSerializer, FlockListSerializer,
    DailyEntrySerializer, SaleSerializer, FeedRateSerializer,
    MedicationSerializer
)


class FarmViewSet(viewsets.ModelViewSet):
    queryset = Farm.objects.all()
    serializer_class = FarmSerializer


class FlockViewSet(viewsets.ModelViewSet):
    queryset = Flock.objects.select_related('farm').all()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return FlockSerializer
        return FlockListSerializer


class DailyEntryViewSet(viewsets.ModelViewSet):
    queryset = DailyEntry.objects.select_related('flock', 'flock__farm').all()
    serializer_class = DailyEntrySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        flock_id = self.request.query_params.get('flock')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.select_related('flock', 'flock__farm').all()
    serializer_class = SaleSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        flock_id = self.request.query_params.get('flock')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs


class FeedRateViewSet(viewsets.ModelViewSet):
    queryset = FeedRate.objects.all()
    serializer_class = FeedRateSerializer


class MedicationViewSet(viewsets.ModelViewSet):
    queryset = Medication.objects.all()
    serializer_class = MedicationSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        flock_id = self.request.query_params.get('flock')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs


@api_view(['GET'])
def dashboard(request):
    """Main integration-level dashboard."""
    farms = Farm.objects.all()
    all_flocks = Flock.objects.all()
    active_flocks = all_flocks.filter(status='active')

    # Birds placed till date (all flocks ever)
    total_birds_placed = all_flocks.aggregate(t=Sum('chick_count'))['t'] or 0

    # Mortality till date (all flocks)
    total_mortality = DailyEntry.objects.aggregate(t=Sum('mortality_count'))['t'] or 0

    # Sold till date
    total_sold_birds = Sale.objects.aggregate(t=Sum('bird_count'))['t'] or 0
    total_sold_weight_kg = Sale.objects.aggregate(t=Sum('total_weight_kg'))['t'] or Decimal('0')
    total_sale_amount = Decimal('0')
    for sale in Sale.objects.filter(rate_per_kg__isnull=False):
        total_sale_amount += sale.total_weight_kg * sale.rate_per_kg

    # Feed till date
    total_feed_kg = DailyEntry.objects.aggregate(t=Sum('feed_consumed_kg'))['t'] or Decimal('0')

    # FCR till date = total feed / total weight sold
    fcr = None
    if total_sold_weight_kg and total_sold_weight_kg > 0:
        fcr = round(float(total_feed_kg) / float(total_sold_weight_kg), 3)

    # Current feed rate (latest)
    latest_feed_rate = FeedRate.objects.first()

    # Cost per kg production = (total feed kg * avg feed rate) / total sold weight
    # Simplified: using latest feed rate
    cost_per_kg = None
    if latest_feed_rate and total_sold_weight_kg and total_sold_weight_kg > 0:
        total_feed_cost = float(total_feed_kg) * float(latest_feed_rate.rate_per_kg)
        cost_per_kg = round(total_feed_cost / float(total_sold_weight_kg), 2)

    # Today's entries
    today = date.today()
    today_entries = DailyEntry.objects.filter(date=today)
    mortality_today = today_entries.aggregate(t=Sum('mortality_count'))['t'] or 0
    feed_today = today_entries.aggregate(t=Sum('feed_consumed_kg'))['t'] or 0

    # Live birds across active flocks
    total_live_birds = 0
    for flock in active_flocks:
        total_live_birds += flock.live_birds

    data = {
        # Summary cards
        'total_birds_placed': total_birds_placed,
        'total_sold_birds': total_sold_birds,
        'total_sold_weight_kg': float(total_sold_weight_kg),
        'total_sale_amount': float(total_sale_amount),
        'total_mortality': total_mortality,
        'mortality_percentage': round((total_mortality / total_birds_placed) * 100, 2) if total_birds_placed else 0,
        'total_feed_kg': float(total_feed_kg),
        'fcr': fcr,
        'cost_per_kg_production': cost_per_kg,
        'current_feed_rate': float(latest_feed_rate.rate_per_kg) if latest_feed_rate else None,

        # Active status
        'total_farms': farms.count(),
        'total_active_flocks': active_flocks.count(),
        'total_live_birds': total_live_birds,
        'mortality_today': mortality_today,
        'feed_today': float(feed_today),

        # Feed rate history
        'feed_rates': FeedRateSerializer(FeedRate.objects.all()[:10], many=True).data,

        # Farm details
        'farms': FarmSerializer(farms, many=True).data,
    }
    return Response(data)


@api_view(['GET'])
def flock_cumulative(request, flock_id):
    """Returns day-by-day cumulative data for charts."""
    entries = DailyEntry.objects.filter(flock_id=flock_id).order_by('date')
    flock = Flock.objects.get(id=flock_id)
    sales = Sale.objects.filter(flock_id=flock_id).order_by('date')

    cumulative_mortality = 0
    cumulative_feed = 0
    result = []

    for entry in entries:
        cumulative_mortality += entry.mortality_count
        cumulative_feed += float(entry.feed_consumed_kg)
        day_number = (entry.date - flock.placement_date).days

        result.append({
            'date': entry.date,
            'day_number': day_number,
            'daily_mortality': entry.mortality_count,
            'cumulative_mortality': cumulative_mortality,
            'mortality_percentage': round((cumulative_mortality / flock.chick_count) * 100, 2) if flock.chick_count else 0,
            'daily_feed_kg': float(entry.feed_consumed_kg),
            'cumulative_feed_kg': round(cumulative_feed, 2),
            'water_liters': float(entry.water_consumed_liters),
            'avg_body_weight_grams': float(entry.avg_body_weight_grams) if entry.avg_body_weight_grams else None,
        })

    return Response({
        'flock_id': flock.id,
        'farm_name': flock.farm.name,
        'breed': flock.breed,
        'placement_date': flock.placement_date,
        'chick_count': flock.chick_count,
        'age_days': flock.age_days,
        'total_mortality': flock.total_mortality,
        'total_feed_kg': float(flock.total_feed_kg),
        'total_sold_birds': flock.total_sold_birds,
        'total_sold_weight_kg': float(flock.total_sold_weight_kg),
        'live_birds': flock.live_birds,
        'fcr': flock.fcr,
        'entries': result,
        'sales': SaleSerializer(sales, many=True).data,
    })
