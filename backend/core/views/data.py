"""Farm / Flock / DailyEntry / Sale / FeedRate / Medication CRUD viewsets."""
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from datetime import date

from ..models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication
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
        from rest_framework.exceptions import ValidationError
        farm = serializer.validated_data.get('farm')
        chick_count = serializer.validated_data.get('chick_count', 0)

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

    def _validate_entry(self, data, instance=None):
        from rest_framework.exceptions import ValidationError
        flock = data.get('flock') or (instance.flock if instance else None)
        if not flock:
            return

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
        serializer.save()

    def perform_update(self, serializer):
        self._validate_entry(serializer.validated_data, instance=serializer.instance)
        serializer.save()


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

    def perform_create(self, serializer):
        from rest_framework.exceptions import ValidationError
        flock = serializer.validated_data.get('flock')
        bird_count = serializer.validated_data.get('bird_count', 0)
        sale_date = serializer.validated_data.get('date')

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
        serializer.save()


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
