from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal

from ..models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication, FeedOrder
from ..serializers import (
    FarmSerializer, FlockSerializer, FlockListSerializer,
    DailyEntrySerializer, SaleSerializer, FeedRateSerializer,
    MedicationSerializer
)
from ..permissions import IsAdminOrReadOnly, CanEditFarm, CanEditFlock, CanEditFlockData


class FarmViewSet(viewsets.ModelViewSet):
    queryset = Farm.objects.all()
    serializer_class = FarmSerializer
    permission_classes = [IsAuthenticated, CanEditFarm]

    def perform_create(self, serializer):
        profile = self.request.user.profile
        if not profile.is_admin:
            assigned_regions = set(
                profile.assigned_farms.exclude(region='').values_list('region', flat=True).distinct()
            )
            new_region = serializer.validated_data.get('region', '')
            if not new_region:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'region': 'Region is required.'})
            if assigned_regions and new_region not in assigned_regions:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'region': f'You can only create farms in your assigned regions: {", ".join(sorted(assigned_regions))}'})
            farm = serializer.save()
            profile.assigned_farms.add(farm)
        else:
            serializer.save()


class FlockViewSet(viewsets.ModelViewSet):
    queryset = Flock.objects.select_related('farm').all()
    permission_classes = [IsAuthenticated, CanEditFlock]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return FlockSerializer
        return FlockListSerializer

    def perform_create(self, serializer):
        serializer.save()


class DailyEntryViewSet(viewsets.ModelViewSet):
    queryset = DailyEntry.objects.select_related('flock', 'flock__farm').all()
    serializer_class = DailyEntrySerializer
    permission_classes = [IsAuthenticated, CanEditFlockData]

    def get_queryset(self):
        qs = super().get_queryset()
        flock_id = self.request.query_params.get('flock')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.select_related('flock', 'flock__farm').all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated, CanEditFlockData]

    def get_queryset(self):
        qs = super().get_queryset()
        flock_id = self.request.query_params.get('flock')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs


class FeedRateViewSet(viewsets.ModelViewSet):
    queryset = FeedRate.objects.all()
    serializer_class = FeedRateSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]


class MedicationViewSet(viewsets.ModelViewSet):
    queryset = Medication.objects.select_related('flock', 'flock__farm').all()
    serializer_class = MedicationSerializer
    permission_classes = [IsAuthenticated, CanEditFlockData]

    def get_queryset(self):
        qs = super().get_queryset()
        flock_id = self.request.query_params.get('flock')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs


# ─── DASHBOARD ───

@api_view(['GET'])
def dashboard(request):
    today = date.today()
    farms = Farm.objects.all()
    active_flocks = Flock.objects.filter(status='active').select_related('farm')

    total_live_birds = 0
    mortality_today = 0

    for flock in active_flocks:
        total_live_birds += flock.live_birds
        today_entry = DailyEntry.objects.filter(flock=flock, date=today).first()
        if today_entry:
            mortality_today += today_entry.mortality_count

    today_feed = DailyEntry.objects.filter(date=today).aggregate(
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
        'total_active_flocks': active_flocks.count(),
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
    for flock in active_flocks.select_related('farm'):
        today_entry = DailyEntry.objects.filter(flock=flock, date=today).first()

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

    # Low feed stock — only active feed type
    for farm in farms:
        active_flock = farm.flocks.filter(status='active').first()
        if not active_flock:
            continue
        fs = active_flock.feed_schedule_status
        current_type = fs.get('current_feed_type', 'BFP')
        delivered = FeedOrder.objects.filter(farm=farm, status='delivered', feed_type=current_type).aggregate(t=Sum('quantity_bags'))['t'] or 0
        consumed_map = {'BPSC': 'bpsc', 'BSC': 'bsc', 'BFP': 'bfp'}
        consumed = DailyEntry.objects.filter(flock__farm=farm).aggregate(
            bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'),
        )
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
def flock_cumulative(request, flock_id):
    from ..standards import get_standard_weight

    entries = DailyEntry.objects.filter(flock_id=flock_id).order_by('date')
    flock = Flock.objects.get(id=flock_id)
    sales = Sale.objects.filter(flock_id=flock_id).order_by('date')

    BAG_KG = 50
    cum_mortality = 0
    cum_bpsc = 0
    cum_bsc = 0
    cum_bfp = 0
    result_entries = []

    for entry in entries:
        cum_mortality += entry.mortality_count
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
            'cumulative_mortality': cum_mortality,
            'mortality_percentage': round((cum_mortality / flock.chick_count) * 100, 2) if flock.chick_count > 0 else 0,
            'feed_bpsc_bags': entry.feed_bpsc_bags,
            'feed_bsc_bags': entry.feed_bsc_bags,
            'feed_bfp_bags': entry.feed_bfp_bags,
            'daily_feed_bags': entry.feed_bpsc_bags + entry.feed_bsc_bags + entry.feed_bfp_bags,
            'cumulative_feed_bags': total_bags,
            'cumulative_feed_kg': total_bags * BAG_KG,
            'water_liters': float(entry.water_consumed_liters),
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
        'mortality_percentage': round((cum_mortality / flock.chick_count) * 100, 2) if flock.chick_count > 0 else 0,
        'live_birds': flock.chick_count - cum_mortality - total_sold_birds,
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
        'fcr': fcr,
        'total_medication_cost': float(sum(m.cost for m in meds)),
        'standard_curve': standard_curve,
        'entries': result_entries,
        'sales': result_sales,
        'medications': result_meds,
    })


@api_view(['GET'])
def farm_cumulative(request, farm_id):
    farm = Farm.objects.get(id=farm_id)
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

@api_view(['GET'])
def monthly_report(request):
    from datetime import datetime
    year = int(request.query_params.get('year', date.today().year))
    month = int(request.query_params.get('month', date.today().month))
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

        # Weekly mortality
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

    import calendar
    month_name = calendar.month_name[month]
    return Response({
        'year': year, 'month': month, 'month_name': month_name,
        'flocks_count': len(batches),
        'flocks': batches,
    })


@api_view(['GET'])
def export_monthly_report(request):
    import openpyxl
    from io import BytesIO
    from django.http import HttpResponse

    year = int(request.query_params.get('year', date.today().year))
    month = int(request.query_params.get('month', date.today().month))

    report = monthly_report(request)
    batches = report.data['batches']

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Monthly Report {year}-{month:02d}"
    headers = ['Farm Code', 'Farm Name', 'Owner', 'Region', 'Shed', 'Placed', 'Chicks',
               'Age', 'Mortality', 'Mort%', 'Birds Sold', 'Weight Sold', 'Feed Bags', 'Feed Kg', 'FCR', 'Cost/Kg']
    ws.append(headers)

    for b in batches:
        ws.append([
            b['farm_code'], b['farm_name'], b['owner'], b['region'], b['shed_type'],
            b['placement_date'], b['chick_count'], b['age_days'],
            b['total_mortality'], b['mortality_pct'],
            b['sold_birds'], b['sold_weight'],
            b['total_feed_bags'], b['total_feed_kg'], b['fcr'], b['cost_per_kg'],
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
