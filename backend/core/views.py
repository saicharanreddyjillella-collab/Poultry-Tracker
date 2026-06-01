from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Sum
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


def get_latest_feed_rates():
    """Get the most recent rate for each feed type."""
    rates = {}
    for ft in ['BPSC', 'BSC', 'BFP']:
        latest = FeedRate.objects.filter(feed_type=ft).first()
        if latest:
            rates[ft] = float(latest.rate_per_kg)
    return rates


@api_view(['GET'])
def dashboard(request):
    farms = Farm.objects.all()
    all_flocks = Flock.objects.all()
    active_flocks = all_flocks.filter(status='active')

    total_birds_placed = all_flocks.aggregate(t=Sum('chick_count'))['t'] or 0
    total_mortality = DailyEntry.objects.aggregate(t=Sum('mortality_count'))['t'] or 0

    # Sold
    total_sold_birds = Sale.objects.aggregate(t=Sum('bird_count'))['t'] or 0
    total_sold_weight_kg = Sale.objects.aggregate(t=Sum('total_weight_kg'))['t'] or Decimal('0')
    total_sale_amount = Decimal('0')
    for sale in Sale.objects.filter(rate_per_kg__isnull=False):
        total_sale_amount += sale.total_weight_kg * sale.rate_per_kg

    # Feed by type
    feed_agg = DailyEntry.objects.aggregate(
        bpsc=Sum('feed_bpsc_kg'), bsc=Sum('feed_bsc_kg'), bfp=Sum('feed_bfp_kg'),
    )
    total_bpsc = float(feed_agg['bpsc'] or 0)
    total_bsc = float(feed_agg['bsc'] or 0)
    total_bfp = float(feed_agg['bfp'] or 0)
    total_feed_kg = total_bpsc + total_bsc + total_bfp

    # FCR
    fcr = None
    if total_sold_weight_kg and total_sold_weight_kg > 0:
        fcr = round(total_feed_kg / float(total_sold_weight_kg), 3)

    # Cost per kg using latest rates per feed type
    latest_rates = get_latest_feed_rates()
    total_feed_cost = (
        total_bpsc * latest_rates.get('BPSC', 0) +
        total_bsc * latest_rates.get('BSC', 0) +
        total_bfp * latest_rates.get('BFP', 0)
    )
    cost_per_kg = None
    if total_sold_weight_kg and total_sold_weight_kg > 0:
        cost_per_kg = round(total_feed_cost / float(total_sold_weight_kg), 2)

    # Today
    today = date.today()
    today_entries = DailyEntry.objects.filter(date=today)
    mortality_today = today_entries.aggregate(t=Sum('mortality_count'))['t'] or 0
    today_feed = today_entries.aggregate(
        bpsc=Sum('feed_bpsc_kg'), bsc=Sum('feed_bsc_kg'), bfp=Sum('feed_bfp_kg'),
    )

    total_live_birds = sum(f.live_birds for f in active_flocks)

    data = {
        'total_birds_placed': total_birds_placed,
        'total_sold_birds': total_sold_birds,
        'total_sold_weight_kg': float(total_sold_weight_kg),
        'total_sale_amount': float(total_sale_amount),
        'total_mortality': total_mortality,
        'mortality_percentage': round((total_mortality / total_birds_placed) * 100, 2) if total_birds_placed else 0,

        'total_feed_kg': round(total_feed_kg, 2),
        'feed_by_type': {
            'bpsc': round(total_bpsc, 2),
            'bsc': round(total_bsc, 2),
            'bfp': round(total_bfp, 2),
        },
        'total_feed_cost': round(total_feed_cost, 2),
        'fcr': fcr,
        'cost_per_kg_production': cost_per_kg,

        'latest_feed_rates': latest_rates,

        'total_farms': farms.count(),
        'total_active_flocks': active_flocks.count(),
        'total_live_birds': total_live_birds,
        'mortality_today': mortality_today,
        'feed_today': {
            'bpsc': float(today_feed['bpsc'] or 0),
            'bsc': float(today_feed['bsc'] or 0),
            'bfp': float(today_feed['bfp'] or 0),
        },

        'feed_rates': FeedRateSerializer(FeedRate.objects.all()[:30], many=True).data,
        'farms': FarmSerializer(farms, many=True).data,
    }
    return Response(data)


@api_view(['GET'])
def flock_cumulative(request, flock_id):
    entries = DailyEntry.objects.filter(flock_id=flock_id).order_by('date')
    flock = Flock.objects.get(id=flock_id)
    sales = Sale.objects.filter(flock_id=flock_id).order_by('date')

    cum_mortality = 0
    cum_bpsc = cum_bsc = cum_bfp = 0
    result = []

    for entry in entries:
        cum_mortality += entry.mortality_count
        cum_bpsc += float(entry.feed_bpsc_kg)
        cum_bsc += float(entry.feed_bsc_kg)
        cum_bfp += float(entry.feed_bfp_kg)
        cum_feed = cum_bpsc + cum_bsc + cum_bfp
        day_number = (entry.date - flock.placement_date).days

        result.append({
            'date': entry.date,
            'day_number': day_number,
            'daily_mortality': entry.mortality_count,
            'cumulative_mortality': cum_mortality,
            'mortality_percentage': round((cum_mortality / flock.chick_count) * 100, 2) if flock.chick_count else 0,
            'feed_bpsc_kg': float(entry.feed_bpsc_kg),
            'feed_bsc_kg': float(entry.feed_bsc_kg),
            'feed_bfp_kg': float(entry.feed_bfp_kg),
            'daily_feed_kg': entry.total_feed_kg,
            'cumulative_feed_kg': round(cum_feed, 2),
            'cum_bpsc': round(cum_bpsc, 2),
            'cum_bsc': round(cum_bsc, 2),
            'cum_bfp': round(cum_bfp, 2),
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
        'feed_by_type': flock.feed_by_type,
        'feed_schedule_status': flock.feed_schedule_status,
        'total_sold_birds': flock.total_sold_birds,
        'total_sold_weight_kg': float(flock.total_sold_weight_kg),
        'live_birds': flock.live_birds,
        'fcr': flock.fcr,
        'entries': result,
        'sales': SaleSerializer(sales, many=True).data,
    })
