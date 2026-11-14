"""Monthly / region / till-date reports and Excel exports."""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Sum
from datetime import date
from decimal import Decimal

from ..models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication
from ..serializers import FeedRateSerializer


def _compute_monthly_report(year, month):
    """Core monthly report logic — returns dict. Callable without a request."""
    import calendar
    BAG_KG = 50
    flocks = Flock.objects.filter(status='closed').select_related('farm')
    batches = []

    for flock in flocks:
        sales = Sale.objects.filter(flock=flock)
        sale_months = sales.values_list('date', flat=True)
        if not any(d.year == year and d.month == month for d in sale_months):
            continue

        entries = DailyEntry.objects.filter(flock=flock)
        total_mort = entries.aggregate(t=Sum('mortality_count'))['t'] or 0
        feed_agg = entries.aggregate(
            bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'),
        )
        total_bags = (feed_agg['bpsc'] or 0) + (feed_agg['bsc'] or 0) + (feed_agg['bfp'] or 0)
        total_feed_kg = total_bags * BAG_KG
        sold_birds = sales.aggregate(t=Sum('bird_count'))['t'] or 0
        sold_weight = float(sales.aggregate(t=Sum('total_weight_kg'))['t'] or 0)
        fcr = round(total_feed_kg / sold_weight, 3) if sold_weight > 0 else None
        cost_kg = None
        if sold_weight > 0:
            chick_cost = flock.chick_count * 34
            feed_cost = total_feed_kg * 44
            med_cost = float(flock.total_medication_cost)
            admin_cost = sold_birds * 6
            cost_kg = round((chick_cost + feed_cost + med_cost + admin_cost) / sold_weight, 2)

        weekly_mort = []
        for entry in entries.order_by('date'):
            week = ((entry.date - flock.placement_date).days) // 7 + 1
            if week > len(weekly_mort):
                weekly_mort.extend([0] * (week - len(weekly_mort)))
            weekly_mort[week - 1] += entry.mortality_count

        batches.append({
            'flock_id': flock.id, 'farm_code': flock.farm.farm_code,
            'farm_name': flock.farm.name, 'owner': flock.farm.owner_name,
            'region': flock.farm.region, 'shed_type': flock.farm.shed_type,
            'placement_date': str(flock.placement_date),
            'chick_count': flock.chick_count,
            'age_days': flock.age_days,
            'total_mortality': total_mort,
            'mortality_pct': round((total_mort / flock.chick_count) * 100, 2) if flock.chick_count > 0 else 0,
            'total_sold_birds': sold_birds,
            'total_sold_weight_kg': sold_weight,
            'avg_bird_weight_kg': round(sold_weight / sold_birds, 3) if sold_birds > 0 else None,
            'total_feed_bags': total_bags, 'total_feed_kg': total_feed_kg,
            'feed_cost': round(total_feed_kg * 44, 2),
            'fcr': fcr,
            'cost_per_kg_production': cost_kg,
            'weekly_mortality': weekly_mort,
        })

    return {
        'year': year, 'month': month, 'month_name': calendar.month_name[month],
        'flocks_count': len(batches),
        'flocks': batches,
    }


@api_view(['GET'])
def monthly_report(request):
    year = int(request.query_params.get('year', date.today().year))
    month = int(request.query_params.get('month', date.today().month))
    return Response(_compute_monthly_report(year, month))


@api_view(['GET'])
def export_monthly_report(request):
    import openpyxl
    from io import BytesIO
    from django.http import HttpResponse

    year = int(request.query_params.get('year', date.today().year))
    month = int(request.query_params.get('month', date.today().month))

    report = _compute_monthly_report(year, month)
    batches = report['flocks']

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Monthly {year}-{month:02d}"
    headers = ['Farm Code', 'Farm Name', 'Owner', 'Region', 'Shed', 'Placed', 'Chicks',
               'Age', 'Mortality', 'Mort%', 'Birds Sold', 'Weight Sold', 'Avg Wt', 'Feed Bags', 'Feed Kg', 'FCR', 'Cost/Kg']
    ws.append(headers)

    for b in batches:
        ws.append([
            b['farm_code'], b['farm_name'], b['owner'], b['region'], b['shed_type'],
            b['placement_date'], b['chick_count'], b['age_days'],
            b['total_mortality'], b['mortality_pct'],
            b['total_sold_birds'], b['total_sold_weight_kg'], b['avg_bird_weight_kg'],
            b['total_feed_bags'], b['total_feed_kg'], b['fcr'], b['cost_per_kg_production'],
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="monthly_report_{year}_{month:02d}.xlsx"'
    return response


@api_view(['GET'])
def export_flock_report(request, flock_id):
    import openpyxl
    from io import BytesIO
    from django.http import HttpResponse
    from ..standards import get_standard_weight

    flock = Flock.objects.select_related('farm').get(id=flock_id)
    entries = DailyEntry.objects.filter(flock=flock).order_by('date')
    sales = Sale.objects.filter(flock=flock).order_by('date')
    meds = Medication.objects.filter(flock=flock).order_by('date')

    BAG_KG = 50
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Flock Report"

    # Header
    ws.append(['Farm', flock.farm.name])
    ws.append(['Farm Code', flock.farm.farm_code])
    ws.append(['Owner', flock.farm.owner_name])
    ws.append(['Placement Date', str(flock.placement_date)])
    ws.append(['Chicks Placed', flock.chick_count])
    ws.append(['Age (days)', flock.age_days])
    ws.append(['Status', flock.status])
    ws.append([])

    # Daily entries
    ws.append(['Day', 'Date', 'Mortality', 'Cum Mort', 'Mort%', 'Feed Type', 'Bags', 'Cum Bags', 'Cum Kg', 'Water(L)', 'Weight(g)', 'Std(g)'])
    cum_mort = 0
    cum_bags = 0
    for entry in entries:
        cum_mort += entry.mortality_count
        day_bags = entry.feed_bpsc_bags + entry.feed_bsc_bags + entry.feed_bfp_bags
        cum_bags += day_bags
        day_num = (entry.date - flock.placement_date).days
        feed_type = 'BPSC' if entry.feed_bpsc_bags > 0 else 'BSC' if entry.feed_bsc_bags > 0 else 'BFP' if entry.feed_bfp_bags > 0 else ''
        bags = entry.feed_bpsc_bags or entry.feed_bsc_bags or entry.feed_bfp_bags or 0
        mort_pct = round((cum_mort / flock.chick_count) * 100, 2) if flock.chick_count > 0 else 0
        ws.append([
            day_num, str(entry.date), entry.mortality_count, cum_mort, mort_pct,
            feed_type, bags, cum_bags, cum_bags * BAG_KG,
            float(entry.water_consumed_liters),
            float(entry.avg_body_weight_grams) if entry.avg_body_weight_grams else None,
            get_standard_weight(day_num),
        ])

    # Sales
    ws.append([])
    ws.append(['SALES'])
    ws.append(['Date', 'Trader', 'Birds', 'Weight (kg)', 'Avg/Bird', 'Rate', 'Amount'])
    for s in sales:
        avg = round(float(s.total_weight_kg) / s.bird_count, 3) if s.bird_count > 0 else 0
        amt = round(float(s.total_weight_kg) * float(s.rate_per_kg), 2) if s.rate_per_kg else None
        ws.append([str(s.date), s.trader_name, s.bird_count, float(s.total_weight_kg), avg, float(s.rate_per_kg) if s.rate_per_kg else None, amt])

    # Medications
    if meds.exists():
        ws.append([])
        ws.append(['MEDICATIONS'])
        ws.append(['Date', 'Name', 'Dose', 'Route', 'Cost', 'Reason'])
        for m in meds:
            ws.append([str(m.date), m.name, m.dose, m.route, float(m.cost), m.reason])

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="flock_{flock_id}_report.xlsx"'
    return response


@api_view(['GET'])
def region_performance(request):
    BAG_KG = 50
    region_filter = request.query_params.get('region')
    farms = Farm.objects.all()
    if region_filter:
        farms = farms.filter(region=region_filter)

    regions = farms.values_list('region', flat=True).distinct()
    result = []

    for region in regions:
        if not region:
            continue
        region_farms = farms.filter(region=region)
        closed = Flock.objects.filter(farm__in=region_farms, status='closed')
        if not closed.exists():
            continue

        total_placed = 0
        total_mort = 0
        total_sold_weight = Decimal('0')
        total_feed_kg = 0
        total_sold_birds = 0

        for flock in closed:
            total_placed += flock.chick_count
            entries = DailyEntry.objects.filter(flock=flock)
            total_mort += entries.aggregate(t=Sum('mortality_count'))['t'] or 0
            feed = entries.aggregate(bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'))
            total_feed_kg += ((feed['bpsc'] or 0) + (feed['bsc'] or 0) + (feed['bfp'] or 0)) * BAG_KG
            sales = Sale.objects.filter(flock=flock)
            total_sold_birds += sales.aggregate(t=Sum('bird_count'))['t'] or 0
            total_sold_weight += sales.aggregate(t=Sum('total_weight_kg'))['t'] or Decimal('0')

        fcr = round(total_feed_kg / float(total_sold_weight), 3) if total_sold_weight > 0 else None

        result.append({
            'region': region,
            'farms': region_farms.count(),
            'batches': closed.count(),
            'total_placed': total_placed,
            'total_mortality': total_mort,
            'mortality_pct': round((total_mort / total_placed) * 100, 2) if total_placed > 0 else 0,
            'total_sold_birds': total_sold_birds,
            'total_sold_weight': float(total_sold_weight),
            'total_feed_kg': total_feed_kg,
            'fcr': fcr,
        })

    return Response({
        'regions': sorted(list(Farm.objects.exclude(region='').values_list('region', flat=True).distinct())),
        'data': result,
    })


# ─── TILL DATE REPORT ───

@api_view(['GET'])
def till_date_report(request):
    BAG_KG = 50
    all_flocks = Flock.objects.select_related('farm').all()
    active_flocks = all_flocks.filter(status='active')

    total_placed = 0
    total_mortality = 0
    total_sold_birds = 0
    total_sold_weight = Decimal('0')
    total_sale_amount = Decimal('0')
    total_bpsc = 0
    total_bsc = 0
    total_bfp = 0
    total_med_cost = Decimal('0')
    total_live_birds = 0

    for flock in all_flocks:
        total_placed += flock.chick_count
        entries = DailyEntry.objects.filter(flock=flock)
        mort = entries.aggregate(t=Sum('mortality_count'))['t'] or 0
        total_mortality += mort

        feed = entries.aggregate(
            bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'),
        )
        total_bpsc += feed['bpsc'] or 0
        total_bsc += feed['bsc'] or 0
        total_bfp += feed['bfp'] or 0

        sales = Sale.objects.filter(flock=flock)
        sold_birds = sales.aggregate(t=Sum('bird_count'))['t'] or 0
        sold_weight = sales.aggregate(t=Sum('total_weight_kg'))['t'] or Decimal('0')
        total_sold_birds += sold_birds
        total_sold_weight += sold_weight

        for s in sales.filter(rate_per_kg__isnull=False):
            total_sale_amount += s.total_weight_kg * s.rate_per_kg

        total_med_cost += Decimal(str(flock.total_medication_cost))

    for flock in active_flocks:
        total_live_birds += flock.live_birds

    total_feed_bags = total_bpsc + total_bsc + total_bfp
    total_feed_kg = total_feed_bags * BAG_KG
    fcr = round(float(total_feed_kg) / float(total_sold_weight), 3) if total_sold_weight > 0 else None
    total_feed_cost = Decimal(str(total_feed_kg)) * Decimal('44')
    cost_per_kg = round(float(total_feed_cost) / float(total_sold_weight), 2) if total_sold_weight > 0 else None

    latest_rates = {}
    for ft in ['BPSC', 'BSC', 'BFP']:
        rate = FeedRate.objects.filter(feed_type=ft).first()
        if rate:
            latest_rates[ft] = str(rate.rate_per_kg)

    return Response({
        'total_birds_placed': total_placed,
        'total_mortality': total_mortality,
        'mortality_percentage': round((total_mortality / total_placed) * 100, 2) if total_placed > 0 else 0,
        'total_sold_birds': total_sold_birds,
        'total_sold_weight_kg': float(total_sold_weight),
        'total_sale_amount': float(total_sale_amount),
        'total_live_birds': total_live_birds,
        'total_feed_bags': total_feed_bags,
        'total_feed_kg': total_feed_kg,
        'feed_by_type': {
            'bpsc_bags': total_bpsc, 'bpsc_kg': total_bpsc * BAG_KG,
            'bsc_bags': total_bsc, 'bsc_kg': total_bsc * BAG_KG,
            'bfp_bags': total_bfp, 'bfp_kg': total_bfp * BAG_KG,
        },
        'fcr': fcr,
        'total_feed_cost': float(total_feed_cost),
        'cost_per_kg_production': cost_per_kg,
        'latest_feed_rates': latest_rates,
        'feed_rates': FeedRateSerializer(FeedRate.objects.all()[:30], many=True).data,
    })

@api_view(['GET'])
def feed_forecast(request):
    """Forward feed-requirement forecast across all active flocks.

    For each active flock and each future day in the horizon, estimate birds
    alive (declining by a standard daily mortality rate) x daily feed intake
    per bird (standard curve), attributed to the feed phase for that age.
    Bucketed by week and phase. Horizon defaults to 4 weeks (28 days).
    """
    from datetime import date, timedelta
    from ..models import Flock, BillConfig
    from ..standards import get_daily_feed_intake, get_feed_phase

    weeks = int(request.query_params.get('weeks', 4))
    weeks = max(1, min(weeks, 12))
    horizon_days = weeks * 7
    BAG_KG = 50

    config = BillConfig.get_active()
    # Standard flock-cycle mortality spread evenly across ~42 days -> daily rate.
    total_mort_pct = float(config.standard_mortality_pct) / 100.0
    daily_mort_rate = total_mort_pct / 42.0

    today = date.today()
    active = Flock.objects.filter(status='active').select_related('farm')

    # buckets[week_index][phase] = kg
    buckets = [{'BPSC': 0.0, 'BSC': 0.0, 'BFP': 0.0} for _ in range(weeks)]
    per_flock = []

    for flock in active:
        live = flock.live_birds
        if live <= 0:
            continue
        flock_total_kg = 0.0
        birds = float(live)
        for d in range(horizon_days):
            day_date = today + timedelta(days=d)
            age = (day_date - flock.placement_date).days
            if age < 0 or age > 56:
                # not yet placed (shouldn't happen for active) or past typical cycle
                birds = birds * (1 - daily_mort_rate)
                continue
            intake_g = get_daily_feed_intake(age)
            kg = (birds * intake_g) / 1000.0
            phase = get_feed_phase(age)
            wk = d // 7
            buckets[wk][phase] += kg
            flock_total_kg += kg
            birds = birds * (1 - daily_mort_rate)
        if flock_total_kg > 0:
            per_flock.append({
                'flock_id': flock.id,
                'farm_code': flock.farm.farm_code,
                'farm_name': flock.farm.name,
                'live_birds': live,
                'forecast_kg': round(flock_total_kg, 1),
                'forecast_bags': round(flock_total_kg / BAG_KG, 1),
            })

    week_rows = []
    grand = {'BPSC': 0.0, 'BSC': 0.0, 'BFP': 0.0}
    for i, b in enumerate(buckets):
        start = today + timedelta(days=i * 7)
        end = today + timedelta(days=i * 7 + 6)
        for ph in ('BPSC', 'BSC', 'BFP'):
            grand[ph] += b[ph]
        total_kg = b['BPSC'] + b['BSC'] + b['BFP']
        week_rows.append({
            'week': i + 1,
            'start': str(start),
            'end': str(end),
            'bpsc_kg': round(b['BPSC'], 1), 'bpsc_bags': round(b['BPSC'] / BAG_KG, 1),
            'bsc_kg': round(b['BSC'], 1), 'bsc_bags': round(b['BSC'] / BAG_KG, 1),
            'bfp_kg': round(b['BFP'], 1), 'bfp_bags': round(b['BFP'] / BAG_KG, 1),
            'total_kg': round(total_kg, 1), 'total_bags': round(total_kg / BAG_KG, 1),
        })

    grand_total_kg = grand['BPSC'] + grand['BSC'] + grand['BFP']
    return Response({
        'generated_on': str(today),
        'weeks': weeks,
        'active_flocks': len(per_flock),
        'weekly': week_rows,
        'totals': {
            'bpsc_kg': round(grand['BPSC'], 1), 'bpsc_bags': round(grand['BPSC'] / BAG_KG, 1),
            'bsc_kg': round(grand['BSC'], 1), 'bsc_bags': round(grand['BSC'] / BAG_KG, 1),
            'bfp_kg': round(grand['BFP'], 1), 'bfp_bags': round(grand['BFP'] / BAG_KG, 1),
            'total_kg': round(grand_total_kg, 1), 'total_bags': round(grand_total_kg / BAG_KG, 1),
        },
        'per_flock': per_flock,
    })
