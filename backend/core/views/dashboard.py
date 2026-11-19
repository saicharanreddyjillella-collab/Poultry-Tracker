"""Dashboard and cumulative (flock / farm) aggregation endpoints."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum
from datetime import date
from decimal import Decimal

from ..models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication, FeedOrder
from ..serializers import FarmSerializer, FeedRateSerializer
from ..access import (NotPlant, deny_plant, is_admin, is_plant, visible_farms, visible_farm_ids,
                      get_visible_farm, get_visible_flock)


@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def dashboard(request):
    today = date.today()
    farms = visible_farms(request.user)
    from ..prime import prime_flocks
    active_flocks = prime_flocks(Flock.objects.filter(status='active', farm__in=farms).select_related('farm'))
    today_entries = {e.flock_id: e for e in DailyEntry.objects.filter(date=today,
                                                                      flock_id__in=[f.id for f in active_flocks])}

    total_live_birds = 0
    mortality_today = 0

    for flock in active_flocks:
        total_live_birds += flock.live_birds
        today_entry = today_entries.get(flock.id)
        if today_entry:
            mortality_today += today_entry.mortality_count

    today_feed = DailyEntry.objects.filter(date=today, flock__farm__in=farms).aggregate(
        bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'),
    )

    # Latest feed rates
    latest_rates = {}
    for ft in ['BPSC', 'BSC', 'BFP']:
        rate = FeedRate.objects.filter(feed_type=ft).first()
        if rate:
            latest_rates[ft] = str(rate.rate_per_kg)

    data = {
        'total_farms': farms.count(),
        'total_active_flocks': len(active_flocks),
        'total_live_birds': total_live_birds,
        'mortality_today': mortality_today,
        'latest_feed_rates': latest_rates,

        'feed_today': {
            'bpsc_bags': float(today_feed['bpsc'] or 0),
            'bsc_bags': float(today_feed['bsc'] or 0),
            'bfp_bags': float(today_feed['bfp'] or 0),
        },

        'feed_rates': FeedRateSerializer(FeedRate.objects.all()[:30], many=True).data,
        'farms': FarmSerializer(farms, many=True).data,
    }

    # ─── ALERTS ───
    alerts = []
    for flock in active_flocks:
        today_entry = today_entries.get(flock.id)

        # High mortality today
        if today_entry and today_entry.mortality_count > 0:
            live = flock.live_birds + today_entry.mortality_count
            if live > 0:
                daily_pct = round((today_entry.mortality_count / live) * 100, 2)
                if daily_pct >= 0.5:
                    alerts.append({
                        'type': 'danger', 'farm_code': flock.farm.farm_code,
                        'farm_name': flock.farm.name, 'flock_id': flock.id,
                        'message': f'{today_entry.mortality_count} deaths today ({daily_pct}%)',
                    })

        # Flock nearing sale age
        if flock.age_days >= 35:
            alerts.append({
                'type': 'warning', 'farm_code': flock.farm.farm_code,
                'farm_name': flock.farm.name, 'flock_id': flock.id,
                'message': f'Day {flock.age_days} — nearing sale age',
            })

        # High cumulative mortality
        if flock.mortality_percentage > 5:
            alerts.append({
                'type': 'danger', 'farm_code': flock.farm.farm_code,
                'farm_name': flock.farm.name, 'flock_id': flock.id,
                'message': f'Cumulative mortality {flock.mortality_percentage}%',
            })

        # No entry today
        if not today_entry:
            alerts.append({
                'type': 'info', 'farm_code': flock.farm.farm_code,
                'farm_name': flock.farm.name, 'flock_id': flock.id,
                'message': 'No daily entry recorded today',
            })

    # Low feed stock — only active feed type (farm totals, loaded for all farms at once)
    first_active = {}
    for f in sorted(active_flocks, key=lambda f: f.id):
        first_active.setdefault(f.farm_id, f)
    farm_ids = list(first_active)
    delivered_by = {(r['farm_id'], r['feed_type']): r['t'] for r in
                    FeedOrder.objects.filter(farm_id__in=farm_ids, status='delivered')
                    .values('farm_id', 'feed_type').annotate(t=Sum('quantity_bags'))}
    consumed_by = {r['flock__farm_id']: r for r in
                   DailyEntry.objects.filter(flock__farm_id__in=farm_ids).values('flock__farm_id')
                   .annotate(bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'))}
    for farm in farms:
        active_flock = first_active.get(farm.id)
        if not active_flock:
            continue
        fs = active_flock.feed_schedule_status
        current_type = fs.get('current_feed_type', 'BFP')
        delivered = delivered_by.get((farm.id, current_type)) or 0
        consumed_map = {'BPSC': 'bpsc', 'BSC': 'bsc', 'BFP': 'bfp'}
        consumed = consumed_by.get(farm.id) or {'bpsc': None, 'bsc': None, 'bfp': None}
        consumed_bags = float(consumed[consumed_map[current_type]] or 0)
        stock = float(delivered) - consumed_bags
        if stock <= 2:
            alerts.append({
                'type': 'warning', 'farm_code': farm.farm_code,
                'farm_name': farm.name, 'flock_id': active_flock.id,
                'message': f'{current_type} stock low: {round(stock, 1)} bags',
            })

    data['alerts'] = alerts
    return Response(data)


# ─── FLOCK CUMULATIVE ───

@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def flock_cumulative(request, flock_id):
    from ..standards import get_standard_weight

    flock = get_visible_flock(request.user, flock_id)          # 404 if missing / other region
    entries = DailyEntry.objects.filter(flock_id=flock_id).order_by('date')
    sales = Sale.objects.filter(flock_id=flock_id).order_by('date')

    BAG_KG = 50
    cum_mortality = 0
    cum_culls = 0
    cum_bpsc = 0
    cum_bsc = 0
    cum_bfp = 0
    result_entries = []

    for entry in entries:
        cum_mortality += entry.mortality_count
        cum_culls += entry.cull_count
        cum_bpsc += entry.feed_bpsc_bags
        cum_bsc += entry.feed_bsc_bags
        cum_bfp += entry.feed_bfp_bags
        total_bags = cum_bpsc + cum_bsc + cum_bfp
        day_number = (entry.date - flock.placement_date).days

        result_entries.append({
            'id': entry.id,
            'date': str(entry.date),
            'day_number': day_number,
            'daily_mortality': entry.mortality_count,
            'daily_culls': entry.cull_count,
            'cumulative_culls': cum_culls,
            'cumulative_mortality': cum_mortality,
            'mortality_percentage': round((cum_mortality / flock.chick_count) * 100, 2) if flock.chick_count > 0 else 0,
            'feed_bpsc_bags': entry.feed_bpsc_bags,
            'feed_bsc_bags': entry.feed_bsc_bags,
            'feed_bfp_bags': entry.feed_bfp_bags,
            'daily_feed_bags': entry.feed_bpsc_bags + entry.feed_bsc_bags + entry.feed_bfp_bags,
            'cumulative_feed_bags': total_bags,
            'cumulative_feed_kg': total_bags * BAG_KG,
            'water_liters': float(entry.water_consumed_liters),
            'water_feed_ratio': entry.water_feed_ratio,
            'water_feed_status': entry.water_feed_status,
            'avg_body_weight_grams': float(entry.avg_body_weight_grams) if entry.avg_body_weight_grams else None,
            'standard_weight_grams': get_standard_weight(day_number),
        })

    result_sales = [{
        'id': s.id,
        'date': str(s.date),
        'bird_count': s.bird_count,
        'total_weight_kg': float(s.total_weight_kg),
        'avg_weight_kg': round(float(s.total_weight_kg) / s.bird_count, 3) if s.bird_count > 0 else 0,
        'rate_per_kg': float(s.rate_per_kg) if s.rate_per_kg else None,
        'trader_name': s.trader_name,
        'notes': s.notes,
    } for s in sales]

    meds = Medication.objects.filter(flock_id=flock_id).order_by('date')
    result_meds = [{
        'id': m.id, 'date': str(m.date), 'name': m.name,
        'dose': m.dose, 'route': m.route, 'cost': float(m.cost),
        'reason': m.reason,
    } for m in meds]

    total_sold_birds = sum(s.bird_count for s in sales)
    total_sold_weight = sum(float(s.total_weight_kg) for s in sales)
    total_feed_bags = cum_bpsc + cum_bsc + cum_bfp
    total_feed_kg = total_feed_bags * BAG_KG
    fcr = round(total_feed_kg / total_sold_weight, 3) if total_sold_weight > 0 else None

    # Standard weight curve for chart
    from ..standards import get_standard_weight
    max_day = flock.age_days or 42
    standard_curve = [{'day': d, 'weight': get_standard_weight(d)} for d in range(0, max_day + 1)]

    return Response({
        'flock_id': flock.id,
        'farm_id': flock.farm_id,
        'farm_name': flock.farm.name,
        'placement_date': str(flock.placement_date),
        'chick_count': flock.chick_count,
        'age_days': flock.age_days,
        'status': flock.status,
        'total_mortality': cum_mortality,
        'total_culls': cum_culls,
        'reconciliation': flock.reconciliation,
        'weight_vs_standard': flock.weight_vs_standard,
        'scorecard': flock.scorecard,
        'water_alerts': flock.water_alerts,
        'feed_reconciliation': flock.feed_reconciliation,
        'mortality_percentage': round((cum_mortality / flock.chick_count) * 100, 2) if flock.chick_count > 0 else 0,
        'live_birds': flock.chick_count - cum_mortality - cum_culls - total_sold_birds,
        'total_sold_birds': total_sold_birds,
        'total_sold_weight': round(total_sold_weight, 2),
        'total_sold_weight_kg': round(total_sold_weight, 2),
        'total_feed_bags': total_feed_bags,
        'total_feed_kg': total_feed_kg,
        'feed_by_type': {
            'bpsc_bags': cum_bpsc, 'bpsc_kg': cum_bpsc * BAG_KG,
            'bsc_bags': cum_bsc, 'bsc_kg': cum_bsc * BAG_KG,
            'bfp_bags': cum_bfp, 'bfp_kg': cum_bfp * BAG_KG,
        },
        'feed_schedule_status': flock.feed_schedule_status,
        'flock_feed_stock': flock.flock_feed_stock,
        'fcr': fcr,
        'epef': flock.epef,
        'avg_sold_weight_kg': flock.avg_sold_weight_kg,
        'total_medication_cost': float(sum(m.cost for m in meds)),
        'standard_curve': standard_curve,
        'entries': result_entries,
        'sales': result_sales,
        'medications': result_meds,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def farm_cumulative(request, farm_id):
    farm = get_visible_farm(request.user, farm_id)
    closed_flocks = Flock.objects.filter(farm=farm, status='closed')

    BAG_KG = 50
    total_placed = 0
    total_mortality = 0
    total_sold_birds = 0
    total_sold_weight = Decimal('0')
    total_feed_bags = 0
    total_med_cost = Decimal('0')
    batch_count = closed_flocks.count()

    for flock in closed_flocks:
        total_placed += flock.chick_count
        entries = DailyEntry.objects.filter(flock=flock)
        total_mortality += entries.aggregate(t=Sum('mortality_count'))['t'] or 0
        feed = entries.aggregate(
            bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'),
        )
        total_feed_bags += (feed['bpsc'] or 0) + (feed['bsc'] or 0) + (feed['bfp'] or 0)
        sales = Sale.objects.filter(flock=flock)
        total_sold_birds += sales.aggregate(t=Sum('bird_count'))['t'] or 0
        total_sold_weight += sales.aggregate(t=Sum('total_weight_kg'))['t'] or Decimal('0')
        total_med_cost += Decimal(str(flock.total_medication_cost))

    total_feed_kg = total_feed_bags * BAG_KG
    fcr = round(float(total_feed_kg) / float(total_sold_weight), 3) if total_sold_weight > 0 else None

    return Response({
        'farm_id': farm.id, 'farm_name': farm.name,
        'batch_count': batch_count, 'total_placed': total_placed,
        'total_mortality': total_mortality,
        'mortality_pct': round((total_mortality / total_placed) * 100, 2) if total_placed > 0 else 0,
        'total_sold_birds': total_sold_birds,
        'total_sold_weight': float(total_sold_weight),
        'total_feed_bags': total_feed_bags, 'total_feed_kg': total_feed_kg,
        'fcr': fcr, 'total_medication_cost': float(total_med_cost),
    })


# ─── REPORTS ───
