from django.utils import timezone
from rest_framework import viewsets
from ..pagination import GuardedListMixin
from ..access import (NotPlant, deny_plant, is_admin, is_plant, visible_farms, visible_farm_ids,
                      get_visible_farm, get_visible_flock, scoped_farms, report_scope, has_home)


def scope_info(request):
    """Tells the screen which scope it is showing and whether a 'My regions' switch applies."""
    return {'scope': report_scope(request), 'has_home': has_home(request.user)}
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Sum
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from ..models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication, FeedOrder
from ..serializers import (
    FarmSerializer, FlockSerializer, FlockListSerializer,
    DailyEntrySerializer, SaleSerializer, FeedRateSerializer,
    MedicationSerializer
)
from ..edit_window import EditWindowMixin
from ..permissions import IsAdmin, IsAdminOrReadOnly, CanEditFarm, CanEditFlock, CanEditFlockData


class FarmViewSet(viewsets.ModelViewSet):
    queryset = Farm.objects.all()
    serializer_class = FarmSerializer
    permission_classes = [IsAuthenticated, CanEditFarm]

    def get_queryset(self):
        return visible_farms(self.request.user)

    def get_serializer_class(self):
        # Feed mill only needs farm names for orders/stock (no PAN, grower data).
        if is_plant(self.request.user):
            from ..serializers import FarmNameSerializer
            return FarmNameSerializer
        return FarmSerializer

    def perform_update(self, serializer):
        deny_plant(self.request.user)
        serializer.save()

    def perform_destroy(self, instance):
        deny_plant(self.request.user)
        instance.delete()

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        deny_plant(self.request.user)
        profile = self.request.user.profile
        if not profile.is_admin:
            assigned_regions = set(profile.assigned_regions or []) | set(
                profile.assigned_farms.exclude(region='').values_list('region', flat=True).distinct()
            )
            if not assigned_regions:
                raise PermissionDenied('You have no regions assigned — ask an admin to assign one first.')
            new_region = serializer.validated_data.get('region', '')
            if not new_region:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'region': 'Region is required.'})
            if new_region not in assigned_regions:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({'region': f'You can only create farms in your assigned regions: {", ".join(sorted(assigned_regions))}'})
            farm = serializer.save()
            profile.assigned_farms.add(farm)
        else:
            serializer.save()


class FlockViewSet(GuardedListMixin, viewsets.ModelViewSet):
    queryset = Flock.objects.select_related('farm').all()
    permission_classes = [IsAuthenticated, NotPlant, CanEditFlock]
    list_filters = ('farm', 'status')

    def get_queryset(self):
        qs = super().get_queryset().filter(farm_id__in=visible_farm_ids(self.request.user))
        if self.action == 'retrieve':
            from django.db.models import Prefetch
            qs = qs.prefetch_related(*(Prefetch(rel, queryset=model.objects.select_related('entered_by', 'edited_by'))
                                       for rel, model in (('daily_entries', DailyEntry), ('sales', Sale),
                                                          ('medications', Medication))))
        if self.action == 'list':
            farm = self.request.query_params.get('farm')
            status = self.request.query_params.get('status')
            if farm:
                qs = qs.filter(farm_id=farm)
            if status:
                qs = qs.filter(status=status)
        return qs.order_by('-placement_date', '-id')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return FlockSerializer
        return FlockListSerializer

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        farm = serializer.validated_data.get('farm')
        chick_count = serializer.validated_data.get('chick_count', 0)
        if not is_admin(self.request.user) and not self.request.user.profile.can_edit_farm(farm):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You can only add flocks to farms in your regions.')

        # Check total active chicks + new flock <= farm capacity
        existing_active_chicks = sum(
            f.chick_count for f in farm.flocks.filter(status='active')
        )
        remaining = farm.capacity - existing_active_chicks
        if chick_count > remaining:
            raise ValidationError({
                'chick_count': f'Farm capacity is {farm.capacity}. Active flocks have {existing_active_chicks} chicks. '
                               f'Maximum for this flock: {remaining}.'
            })
        if chick_count <= 0:
            raise ValidationError({'chick_count': 'Chick count must be greater than 0.'})

        serializer.save()


class DailyEntryViewSet(EditWindowMixin, GuardedListMixin, viewsets.ModelViewSet):
    model_label = 'DailyEntry'
    queryset = DailyEntry.objects.select_related('flock', 'flock__farm', 'entered_by', 'edited_by').all()
    serializer_class = DailyEntrySerializer
    permission_classes = [IsAuthenticated, NotPlant, CanEditFlockData]

    def get_queryset(self):
        qs = super().get_queryset().filter(flock__farm_id__in=visible_farm_ids(self.request.user))
        flock_id = self.request.query_params.get('flock')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs

    def _validate_entry(self, data, instance=None):
        from rest_framework.exceptions import ValidationError
        flock = data.get('flock') or (instance.flock if instance else None)
        if not flock:
            return
        from ..billlock import assert_flock_unlocked
        assert_flock_unlocked(flock)
        if instance and instance.flock_id != flock.pk:
            assert_flock_unlocked(instance.flock_id)

        entry_date = data.get('date') or (instance.date if instance else None)

        # Date must be on or after placement
        if entry_date and entry_date < flock.placement_date:
            raise ValidationError({'date': f'Date cannot be before placement date ({flock.placement_date}).'})

        # Date must not be in the future
        from datetime import date
        if entry_date and entry_date > date.today():
            raise ValidationError({'date': 'Date cannot be in the future.'})

        # Mortality cannot exceed live birds
        mortality = data.get('mortality_count', 0) or 0
        if mortality > 0:
            total_mort = flock.daily_entries.aggregate(t=Sum('mortality_count'))['t'] or 0
            if instance:
                total_mort -= instance.mortality_count
            total_sold = flock.sales.aggregate(t=Sum('bird_count'))['t'] or 0
            live_birds = flock.chick_count - total_mort - total_sold
            if mortality > live_birds:
                raise ValidationError({
                    'mortality_count': f'Mortality ({mortality}) cannot exceed live birds ({live_birds}).'
                })

        # Feed bags limit — no hard block, frontend confirms high values
        bpsc = data.get('feed_bpsc_bags', 0) or 0
        bsc = data.get('feed_bsc_bags', 0) or 0
        bfp = data.get('feed_bfp_bags', 0) or 0

        # Cannot be negative
        if bpsc < 0 or bsc < 0 or bfp < 0:
            raise ValidationError({'feed_bags': 'Feed bags cannot be negative.'})

        # Water and body weight cannot be negative
        water = data.get('water_consumed_liters', 0) or 0
        if float(water) < 0:
            raise ValidationError({'water_consumed_liters': 'Water cannot be negative.'})
        body_wt = data.get('avg_body_weight_grams')
        if body_wt is not None and float(body_wt) < 0:
            raise ValidationError({'avg_body_weight_grams': 'Body weight cannot be negative.'})

        # Cannot exceed available stock for that feed type
        stock = flock.flock_feed_stock
        # Add back current entry's bags if editing
        if instance:
            stock['bpsc'] += instance.feed_bpsc_bags
            stock['bsc'] += instance.feed_bsc_bags
            stock['bfp'] += instance.feed_bfp_bags

        if bpsc > 0 and bpsc > stock.get('bpsc', 0):
            raise ValidationError({
                'feed_bags': f'Only {stock.get("bpsc", 0)} BPSC bags in stock. Cannot use {bpsc}.'
            })
        if bsc > 0 and bsc > stock.get('bsc', 0):
            raise ValidationError({
                'feed_bags': f'Only {stock.get("bsc", 0)} BSC bags in stock. Cannot use {bsc}.'
            })
        if bfp > 0 and bfp > stock.get('bfp', 0):
            raise ValidationError({
                'feed_bags': f'Only {stock.get("bfp", 0)} BFP bags in stock. Cannot use {bfp}.'
            })

    def perform_create(self, serializer):
        self._validate_entry(serializer.validated_data)
        serializer.save(entered_by=self.request.user)

    def perform_update(self, serializer):
        self._validate_entry(serializer.validated_data, instance=serializer.instance)
        serializer.save(edited_by=self.request.user)


class SaleViewSet(EditWindowMixin, GuardedListMixin, viewsets.ModelViewSet):
    model_label = 'Sale'
    queryset = Sale.objects.select_related('flock', 'flock__farm', 'entered_by', 'edited_by').all()
    serializer_class = SaleSerializer
    permission_classes = [IsAuthenticated, NotPlant, CanEditFlockData]

    def get_queryset(self):
        qs = super().get_queryset().filter(flock__farm_id__in=visible_farm_ids(self.request.user))
        flock_id = self.request.query_params.get('flock')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        flock = serializer.validated_data.get('flock')
        bird_count = serializer.validated_data.get('bird_count', 0)
        sale_date = serializer.validated_data.get('date')
        from ..billlock import assert_flock_unlocked
        assert_flock_unlocked(flock)

        if sale_date and sale_date < flock.placement_date:
            raise ValidationError({'date': f'Sale date cannot be before placement ({flock.placement_date}).'})

        # Birds sold cannot exceed live birds
        total_mort = flock.daily_entries.aggregate(t=Sum('mortality_count'))['t'] or 0
        total_sold = flock.sales.aggregate(t=Sum('bird_count'))['t'] or 0
        live_birds = flock.chick_count - total_mort - total_sold
        if bird_count > live_birds:
            raise ValidationError({
                'bird_count': f'Cannot sell {bird_count} birds. Only {live_birds} live birds available.'
            })
        serializer.save(entered_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(edited_by=self.request.user)


class FeedRateViewSet(viewsets.ModelViewSet):
    queryset = FeedRate.objects.all()
    serializer_class = FeedRateSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def create(self, request, *args, **kwargs):
        """'Update Rate' for a week + feed type that already has a rate corrects
        that rate instead of failing on the unique (week, feed type) rule."""
        week, feed_type = request.data.get('week_start_date'), request.data.get('feed_type')
        existing = FeedRate.objects.filter(week_start_date=week, feed_type=feed_type).first() if week and feed_type else None
        if existing is None:
            return super().create(request, *args, **kwargs)
        serializer = self.get_serializer(existing, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=200)


class MedicationViewSet(EditWindowMixin, GuardedListMixin, viewsets.ModelViewSet):
    model_label = 'Medication'
    queryset = Medication.objects.select_related('flock', 'flock__farm', 'entered_by', 'edited_by').all()
    serializer_class = MedicationSerializer
    permission_classes = [IsAuthenticated, NotPlant, CanEditFlockData]

    def perform_create(self, serializer):
        serializer.save(entered_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(edited_by=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset().filter(flock__farm_id__in=visible_farm_ids(self.request.user))
        flock_id = self.request.query_params.get('flock')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs


# ─── DASHBOARD ───

@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def dashboard(request):
    today = date.today()
    farms = scoped_farms(request)                 # supervisors: their regions unless ?scope=all
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

    if is_admin(request.user):                       # decisions waiting for the admin come first
        from ..models import ChangeRequest
        n = ChangeRequest.objects.filter(status='pending').count()
        if n:
            alerts.insert(0, {'type': 'warning', 'farm_name': 'Approvals', 'link': '/approvals',
                              'message': f"{n} change{'s' if n > 1 else ''} outside the edit window waiting for approval"})
        from ..models import Bill
        nb = Bill.objects.filter(approval_status='pending').count()
        if nb:
            alerts.insert(0, {'type': 'warning', 'farm_name': 'Bills', 'link': '/approvals',
                              'message': f"{nb} bill{'s' if nb > 1 else ''} waiting for approval before payment"})
    data['alerts'] = alerts
    data.update(scope_info(request))
    from ..control_room import control_room          # next actions, trends, regions (no extra per-flock queries)
    data.update(control_room(active_flocks, list(farms), today))
    return Response(data)


# ─── FLOCK CUMULATIVE ───

@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def flock_cumulative(request, flock_id):
    from ..standards import get_standard_weight

    flock = get_visible_flock(request.user, flock_id)          # 404 if missing / other region
    from ..serializers import person
    entries = DailyEntry.objects.filter(flock_id=flock_id).select_related('entered_by', 'edited_by').order_by('date')
    sales = Sale.objects.filter(flock_id=flock_id).select_related('entered_by', 'edited_by').order_by('date')

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
            'entered_by_name': person(entry.entered_by),
            'edited_by_name': person(entry.edited_by),
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
        'entered_by_name': person(s.entered_by),
        'edited_by_name': person(s.edited_by),
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

def _compute_monthly_report(year, month, farm_ids=None):
    """Core monthly report logic — returns dict. Callable without a request.
    farm_ids limits it to those farms (a supervisor's regions); None = all."""
    import calendar
    BAG_KG = 50
    flocks = Flock.objects.filter(status='closed').select_related('farm')
    if farm_ids is not None:
        flocks = flocks.filter(farm_id__in=farm_ids)
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


def _report_scope(request):
    """Farm ids a report covers: None = every farm."""
    return list(scoped_farms(request).values_list('id', flat=True)) if report_scope(request) == 'mine' else None


@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def monthly_report(request):
    year = int(request.query_params.get('year', date.today().year))
    month = int(request.query_params.get('month', date.today().month))
    return Response({**_compute_monthly_report(year, month, _report_scope(request)), **scope_info(request)})


@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def export_monthly_report(request):
    import openpyxl
    from io import BytesIO
    from django.http import HttpResponse

    year = int(request.query_params.get('year', date.today().year))
    month = int(request.query_params.get('month', date.today().month))

    report = _compute_monthly_report(year, month, _report_scope(request))
    batches = report['flocks']

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Monthly {year}-{month:02d}"
    from ..access import is_admin
    show_cost = is_admin(request.user)          # cost per kg is a company cost: admin only
    headers = ['Farm Code', 'Farm Name', 'Owner', 'Region', 'Shed', 'Placed', 'Chicks',
               'Age', 'Mortality', 'Mort%', 'Birds Sold', 'Weight Sold', 'Avg Wt', 'Feed Bags', 'Feed Kg', 'FCR']
    if show_cost:
        headers.append('Cost/Kg')
    ws.append(headers)

    for b in batches:
        ws.append([
            b['farm_code'], b['farm_name'], b['owner'], b['region'], b['shed_type'],
            b['placement_date'], b['chick_count'], b['age_days'],
            b['total_mortality'], b['mortality_pct'],
            b['total_sold_birds'], b['total_sold_weight_kg'], b['avg_bird_weight_kg'],
            b['total_feed_bags'], b['total_feed_kg'], b['fcr'],
        ] + ([b['cost_per_kg_production']] if show_cost else []))

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
@permission_classes([IsAuthenticated, NotPlant])
def export_flock_report(request, flock_id):
    import openpyxl
    from io import BytesIO
    from django.http import HttpResponse
    from ..standards import get_standard_weight

    flock = get_visible_flock(request.user, flock_id)
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
@permission_classes([IsAuthenticated, NotPlant])
def region_performance(request):
    BAG_KG = 50
    region_filter = request.query_params.get('region')
    farms = scoped_farms(request)
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
        'regions': sorted(set(scoped_farms(request).exclude(region='').values_list('region', flat=True))),
        'data': result,
        **scope_info(request),
    })


# ─── TILL DATE REPORT ───

@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def till_date_report(request):
    BAG_KG = 50
    all_flocks = Flock.objects.select_related('farm').filter(farm__in=scoped_farms(request))
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

    from ..prime import prime_flocks
    flocks = prime_flocks(all_flocks)                    # page speed: totals for all flocks in a few queries
    for flock in flocks:
        total_placed += flock.chick_count
        total_mortality += flock.total_mortality
        consumed = flock._stats['consumed']
        total_bpsc += consumed['BPSC'] or 0
        total_bsc += consumed['BSC'] or 0
        total_bfp += consumed['BFP'] or 0
        total_sold_birds += flock.total_sold_birds
        total_sold_weight += flock.total_sold_weight_kg or Decimal('0')
        total_med_cost += Decimal(str(flock.total_medication_cost))

    for weight, rate in Sale.objects.filter(flock_id__in=[f.id for f in flocks], rate_per_kg__isnull=False) \
            .values_list('total_weight_kg', 'rate_per_kg'):
        total_sale_amount += weight * rate

    for flock in flocks:
        if flock.status == 'active':
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
        **scope_info(request),
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
@permission_classes([IsAuthenticated, IsAdmin])   # business-sensitive: admin only
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
    from ..prime import prime_flocks
    active = prime_flocks(Flock.objects.filter(status='active').select_related('farm'))

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


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])   # business-sensitive: admin only
def owner_dashboard(request):
    """Owner BI dashboard: active-cycle overview, region/period summary,
    performance leaderboard, and an alerts feed. Read-only aggregation."""
    from datetime import date, timedelta
    from ..models import Flock, Farm, Bill

    period_days = int(request.query_params.get('period_days', 90))
    period_days = max(7, min(period_days, 730))
    since = date.today() - timedelta(days=period_days)

    from ..prime import prime_flocks
    active = list(Flock.objects.filter(status='active').select_related('farm'))
    # Only closed flocks billed around/after the period start are ever used below (exact cut-off kept in Python).
    closed = list(Flock.objects.filter(status='closed', bill__generated_at__gte=since - timedelta(days=1))
                  .select_related('farm', 'bill'))
    prime_flocks(active + closed)                           # page speed: totals in a few queries

    # ── 1. Active-cycle overview ──
    active_rows = []
    total_live = 0
    for f in active:
        live = f.live_birds
        total_live += live
        sc = f.scorecard
        active_rows.append({
            'flock_id': f.id, 'farm_code': f.farm.farm_code, 'farm_name': f.farm.name,
            'region': f.farm.region, 'age_days': f.age_days, 'live_birds': live,
            'feed_phase': f.feed_schedule_status.get('current_feed_type'),
            'mortality_pct': float(f.mortality_percentage),
            'rating': sc['rating'], 'score': sc['overall_score'],
        })

    # ── 2. Region / period summary (closed flocks billed in the period) ──
    period_closed = [f for f in closed if hasattr(f, 'bill') and f.bill and timezone.localdate(f.bill.generated_at) >= since]
    region_map = {}
    for f in period_closed:
        r = f.farm.region or 'Unassigned'
        agg = region_map.setdefault(r, {
            'region': r, 'flocks': 0, 'birds_placed': 0, 'birds_sold': 0,
            'sold_weight_kg': 0.0, 'feed_kg': 0.0, 'mortality_sum': 0.0,
            'fcr_vals': [], 'epef_vals': [], 'paid': 0.0,
        })
        agg['flocks'] += 1
        agg['birds_placed'] += f.chick_count
        agg['birds_sold'] += f.total_sold_birds
        agg['sold_weight_kg'] += float(f.total_sold_weight_kg)
        agg['feed_kg'] += float(f.total_feed_kg)
        agg['mortality_sum'] += float(f.mortality_percentage)
        if f.fcr is not None:
            agg['fcr_vals'].append(f.fcr)
        if f.epef is not None:
            agg['epef_vals'].append(f.epef)
        agg['paid'] += float(f.bill.amount_paid)

    region_summary = []
    for r, a in sorted(region_map.items()):
        n = a['flocks']
        region_summary.append({
            'region': a['region'], 'flocks': n,
            'birds_placed': a['birds_placed'], 'birds_sold': a['birds_sold'],
            'sold_weight_kg': round(a['sold_weight_kg'], 1),
            'feed_bags': round(a['feed_kg'] / 50, 1),
            'avg_mortality_pct': round(a['mortality_sum'] / n, 2) if n else 0,
            'avg_fcr': round(sum(a['fcr_vals']) / len(a['fcr_vals']), 3) if a['fcr_vals'] else None,
            'avg_epef': round(sum(a['epef_vals']) / len(a['epef_vals']), 1) if a['epef_vals'] else None,
            'settlement_paid': round(a['paid'], 2),
        })

    # ── 3. Performance leaderboard (closed flocks in period, by EPEF) ──
    graded = [f for f in period_closed if f.epef is not None]
    graded.sort(key=lambda f: f.epef, reverse=True)
    def _row(f):
        return {
            'flock_id': f.id, 'farm_code': f.farm.farm_code, 'farm_name': f.farm.name,
            'region': f.farm.region, 'epef': f.epef, 'fcr': f.fcr,
            'livability_pct': float(f.livability_percentage),
            'grade': f.bill.farmer_grade if (hasattr(f, 'bill') and f.bill) else None,
        }
    leaderboard = {
        'top': [_row(f) for f in graded[:5]],
        'bottom': [_row(f) for f in graded[-5:][::-1]] if len(graded) > 5 else [],
    }

    # ── 4. Alerts feed (owner-level, across active flocks) ──
    alerts = []
    today = date.today()
    for f in active:
        # stale data: no entry in 2+ days
        last = f._stats['entries'][0] if f._stats['entries'] else None   # newest first
        if last is None or (today - last.date).days >= 2:
            alerts.append({'type': 'warning', 'flock_id': f.id, 'farm_code': f.farm.farm_code,
                           'farm_name': f.farm.name, 'category': 'stale_data',
                           'message': 'No daily entry in 2+ days'})
        # population mismatch
        rec = f.reconciliation
        if not rec['is_balanced']:
            alerts.append({'type': 'danger', 'flock_id': f.id, 'farm_code': f.farm.farm_code,
                           'farm_name': f.farm.name, 'category': 'population',
                           'message': f"Population mismatch (over by {rec['overcount']})"})
        # weight below target
        w = f.weight_vs_standard
        if w and w['status'] == 'below':
            alerts.append({'type': 'warning', 'flock_id': f.id, 'farm_code': f.farm.farm_code,
                           'farm_name': f.farm.name, 'category': 'weight',
                           'message': f"Weight {w['variance_pct']}% below target (d{w['day']})"})
        # feed variance
        fr = f.feed_reconciliation
        if not fr['is_balanced']:
            alerts.append({'type': 'warning', 'flock_id': f.id, 'farm_code': f.farm.farm_code,
                           'farm_name': f.farm.name, 'category': 'feed_variance',
                           'message': f"Feed {fr['status'].replace('_', ' ')} ({fr['variance_pct']}%)"})
        # water alerts
        if f.water_alerts:
            alerts.append({'type': 'warning', 'flock_id': f.id, 'farm_code': f.farm.farm_code,
                           'farm_name': f.farm.name, 'category': 'water',
                           'message': f"{len(f.water_alerts)} day(s) water:feed out of range"})

    return Response({
        'period_days': period_days,
        'overview': {
            'active_flocks': len(active),
            'total_live_birds': total_live,
            'closed_in_period': len(period_closed),
            'total_farms': Farm.objects.count(),
        },
        'active_cycle': active_rows,
        'region_summary': region_summary,
        'leaderboard': leaderboard,
        'alerts': alerts,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])   # business-sensitive: admin only
def break_even_projection(request):
    """Projected break-even for every ACTIVE flock at current feed rates.

    For each live flock, project to a finish age (default 42 days):
      feed-to-finish = feed consumed so far + remaining intake (standard curve,
                       birds declining by standard daily mortality)
      total cost = chick + feed(kg × current feed rate) + medicine + admin
      projected sold weight = projected live birds at finish × standard
                              finish weight
      cost_per_kg = total cost / projected sold weight
      break_even_price = cost_per_kg (price that just covers production cost)
    Reading live flocks' break-evens is a proxy for what a new placement
    would land at under current rates.
    """
    from datetime import date, timedelta
    from ..models import Flock, BillConfig
    from ..standards import get_daily_feed_intake, get_standard_weight

    finish_age = int(request.query_params.get('finish_age', 42))
    finish_age = max(28, min(finish_age, 56))
    config = BillConfig.get_active()
    BAG_KG = 50
    D = lambda v: Decimal(str(v))

    feed_rate = D(config.feed_cost_per_kg)
    chick_cost = D(config.chick_cost_per_bird)
    admin_cost = D(config.admin_cost_per_chick)
    med_cost = D(config.medicine_cost_per_chick)
    daily_mort = (float(config.standard_mortality_pct) / 100.0) / 42.0
    finish_wt_kg = D(get_standard_weight(finish_age)) / D(1000)

    rows = []
    pool_cost = Decimal('0')
    pool_weight = Decimal('0')
    pool_feed_kg = Decimal('0')
    pool_birds = 0
    pool_chicks = 0
    from ..prime import prime_flocks
    for f in prime_flocks(Flock.objects.filter(status='active').select_related('farm')):
        chicks = f.chick_count
        if chicks <= 0:
            continue
        age = f.age_days
        consumed_kg = D(f.total_feed_kg)

        # Remaining feed from tomorrow to finish_age, birds declining by mortality.
        birds = float(f.live_birds)
        remaining_g = 0.0
        for a in range(age + 1, finish_age + 1):
            remaining_g += birds * get_daily_feed_intake(a)
            birds = birds * (1 - daily_mort)
        remaining_kg = D(remaining_g) / D(1000)
        projected_live = int(round(birds))  # birds alive at finish

        total_feed_kg = (consumed_kg + remaining_kg)
        feed_cost = (total_feed_kg * feed_rate)
        chick_total = D(chicks) * chick_cost
        med_total = D(chicks) * med_cost
        # admin on expected marketed birds (projected live at finish)
        admin_total = D(max(0, projected_live)) * admin_cost
        total_cost = (chick_total + feed_cost + med_total + admin_total)

        projected_weight = D(max(0, projected_live)) * finish_wt_kg
        if projected_weight > 0:
            cost_per_kg = (total_cost / projected_weight).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            cost_per_kg = Decimal('0')

        rows.append({
            'flock_id': f.id, 'farm_code': f.farm.farm_code, 'farm_name': f.farm.name,
            'region': f.farm.region, 'age_days': age,
            'chicks_placed': chicks, 'projected_live_at_finish': max(0, projected_live),
            'feed_consumed_bags': round(float(consumed_kg) / BAG_KG, 1),
            'feed_to_finish_bags': round(float(total_feed_kg) / BAG_KG, 1),
            'projected_weight_kg': round(float(projected_weight), 1),
            'total_cost': round(float(total_cost), 2),
            'cost_per_kg': float(cost_per_kg),
            'break_even_price_per_kg': float(cost_per_kg),
        })
        pool_cost += total_cost
        pool_weight += projected_weight
        pool_feed_kg += total_feed_kg
        pool_birds += max(0, projected_live)
        pool_chicks += chicks

    rows.sort(key=lambda r: r['cost_per_kg'])
    costs = [r['cost_per_kg'] for r in rows if r['cost_per_kg'] > 0]
    avg_cost = round(sum(costs) / len(costs), 2) if costs else 0

    # Blended (pooled) break-even across ALL live flocks: total cost / total
    # projected weight — the true weight-weighted figure (not the mean of
    # per-flock rates).
    if pool_weight > 0:
        blended = (pool_cost / pool_weight).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        blended = Decimal('0')

    return Response({
        'finish_age': finish_age,
        'feed_rate_per_kg': float(feed_rate),
        'rates': {
            'chick_cost_per_bird': float(chick_cost),
            'feed_cost_per_kg': float(feed_rate),
            'admin_cost_per_chick': float(admin_cost),
            'medicine_cost_per_chick': float(med_cost),
        },
        'active_flocks': len(rows),
        'avg_break_even_per_kg': avg_cost,
        'overall': {
            'blended_break_even_per_kg': float(blended),
            'total_cost': round(float(pool_cost), 2),
            'total_projected_weight_kg': round(float(pool_weight), 1),
            'total_feed_to_finish_bags': round(float(pool_feed_kg) / BAG_KG, 1),
            'total_projected_birds': pool_birds,
            'total_chicks_placed': pool_chicks,
        },
        'flocks': rows,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def farm_performance_history(request, farm_id):
    """Multi-cycle performance history for one farm: each closed flock's key
    metrics in placement order, plus averages and a trend direction."""
    from ..models import Farm, Flock

    farm = visible_farms(request.user).filter(id=farm_id).first()
    if farm is None:
        return Response({'error': 'Farm not found'}, status=404)

    flocks = Flock.objects.filter(farm=farm, status='closed').order_by('placement_date')

    cycles = []
    for f in flocks:
        bill = f.bill if hasattr(f, 'bill') else None
        cycles.append({
            'flock_id': f.id,
            'placement_date': str(f.placement_date),
            'chicks_placed': f.chick_count,
            'age_days': f.age_days,
            'fcr': f.fcr,
            'epef': f.epef,
            'livability_pct': float(f.livability_percentage),
            'mortality_pct': float(f.mortality_percentage),
            'cost_per_kg': float(bill.production_cost_per_kg) if bill else None,
            'grade': bill.farmer_grade if bill else None,
            'settlement_paid': float(bill.amount_paid) if bill else None,
        })

    def _avg(key):
        vals = [c[key] for c in cycles if c[key] is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    def _trend(key, higher_is_better):
        """Compare the first vs the last non-null value; returns
        'improving' / 'declining' / 'flat' / None."""
        vals = [c[key] for c in cycles if c[key] is not None]
        if len(vals) < 2:
            return None
        first, last = vals[0], vals[-1]
        if first == last:
            return 'flat'
        better = last > first if higher_is_better else last < first
        return 'improving' if better else 'declining'

    averages = {
        'fcr': _avg('fcr'),
        'epef': _avg('epef'),
        'livability_pct': _avg('livability_pct'),
        'mortality_pct': _avg('mortality_pct'),
        'cost_per_kg': _avg('cost_per_kg'),
        'settlement_paid': _avg('settlement_paid'),
    }
    trends = {
        'fcr': _trend('fcr', higher_is_better=False),         # lower FCR better
        'epef': _trend('epef', higher_is_better=True),        # higher EPEF better
        'livability_pct': _trend('livability_pct', higher_is_better=True),
        'mortality_pct': _trend('mortality_pct', higher_is_better=False),
        'cost_per_kg': _trend('cost_per_kg', higher_is_better=False),
    }

    return Response({
        'farm_id': farm.id,
        'farm_code': farm.farm_code,
        'farm_name': farm.name,
        'region': farm.region,
        'cycle_count': len(cycles),
        'cycles': cycles,
        'averages': averages,
        'trends': trends,
    })
