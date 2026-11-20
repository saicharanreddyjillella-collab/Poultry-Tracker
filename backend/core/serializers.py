from rest_framework import serializers
from .prime import prime_flocks, unprime
from .models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication, FeedOrder, FeedTransfer, BillConfig, Bill, BillVersion, Document, AuditLog


def person(user):
    """Name to show for a user: their full name, else username."""
    if user is None:
        return None
    return user.get_full_name() or user.username


class EnteredByMixin(serializers.Serializer):
    """Who entered a record and who changed it last — set by the server, never by the client."""
    entered_by_name = serializers.SerializerMethodField()
    edited_by_name = serializers.SerializerMethodField()

    def get_entered_by_name(self, obj):
        return person(obj.entered_by)

    def get_edited_by_name(self, obj):
        return person(obj.edited_by)


ENTERED_BY_READ_ONLY = ('entered_by', 'edited_by')


class DailyEntrySerializer(EnteredByMixin, serializers.ModelSerializer):
    total_feed_bags = serializers.ReadOnlyField()

    def validate(self, attrs):
        # E14: one live entry per flock per day (deleted entries don't count).
        flock = attrs.get('flock', getattr(self.instance, 'flock', None))
        day = attrs.get('date', getattr(self.instance, 'date', None))
        if flock is not None and day is not None:
            qs = DailyEntry.objects.filter(flock=flock, date=day)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({'date': f'An entry for {day} already exists for this flock.'})
        return super().validate(attrs)
    total_feed_kg = serializers.ReadOnlyField()
    feed_bpsc_kg = serializers.ReadOnlyField()
    feed_bsc_kg = serializers.ReadOnlyField()
    feed_bfp_kg = serializers.ReadOnlyField()

    class Meta:
        model = DailyEntry
        fields = '__all__'
        read_only_fields = ENTERED_BY_READ_ONLY


class SaleSerializer(EnteredByMixin, serializers.ModelSerializer):
    total_amount = serializers.ReadOnlyField()
    avg_bird_weight_kg = serializers.ReadOnlyField()

    class Meta:
        model = Sale
        fields = '__all__'
        read_only_fields = ENTERED_BY_READ_ONLY


class FeedRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedRate
        fields = '__all__'


class MedicationSerializer(EnteredByMixin, serializers.ModelSerializer):
    class Meta:
        model = Medication
        fields = '__all__'
        read_only_fields = ENTERED_BY_READ_ONLY


class ChickQualityFields(serializers.Serializer):
    """Hatchery, dead-on-arrival and chick weight on a flock — shared checks."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        chicks = attrs.get('chick_count', getattr(self.instance, 'chick_count', None))
        doa = attrs.get('doa_count')
        if doa is not None and chicks is not None and doa > chicks:
            raise serializers.ValidationError({'doa_count': 'Dead on arrival cannot be more than the chicks placed.'})
        w = attrs.get('chick_weight_g')
        if w is not None and not (20 <= w <= 80):
            raise serializers.ValidationError({'chick_weight_g': 'A day-old chick weighs 20–80 g. Check the number.'})
        h = attrs.get('hatchery')
        if h is not None and not h.active and getattr(self.instance, 'hatchery_id', None) != h.id:
            raise serializers.ValidationError({'hatchery': f'{h.name} is no longer used. Pick another hatchery.'})
        return attrs


class PrimedFlocks:
    """Page speed: load every flock's totals in a few queries before serializing, then
    drop them (so a flock instance never keeps stale totals after the response)."""

    def to_representation(self, instance):
        primed_here = getattr(instance, '_stats', None) is None
        if primed_here:
            prime_flocks([instance])
        try:
            return super().to_representation(instance)
        finally:
            if primed_here:
                unprime([instance])


class PrimedFlockList(serializers.ListSerializer):
    def to_representation(self, data):
        items = list(data.all() if hasattr(data, 'all') else data)
        if items and hasattr(items[0], 'farm_id'):
            from django.db.models import prefetch_related_objects
            prefetch_related_objects([f for f in items if 'farm' not in f._state.fields_cache], 'farm')
            prefetch_related_objects([f for f in items if 'supervisor' not in f._state.fields_cache], 'supervisor')
        fresh = [f for f in items if getattr(f, '_stats', None) is None]
        prime_flocks(fresh)
        try:
            return super().to_representation(items)
        finally:
            unprime(fresh)


class FlockSerializer(PrimedFlocks, ChickQualityFields, serializers.ModelSerializer):
    hatchery_name = serializers.CharField(source='hatchery.name', read_only=True, default=None)
    age_days = serializers.ReadOnlyField()
    total_mortality = serializers.ReadOnlyField()
    total_feed_kg = serializers.ReadOnlyField()
    feed_by_type = serializers.ReadOnlyField()
    feed_schedule_status = serializers.ReadOnlyField()
    total_sold_birds = serializers.ReadOnlyField()
    total_sold_weight_kg = serializers.ReadOnlyField()
    mortality_percentage = serializers.ReadOnlyField()
    livability_percentage = serializers.ReadOnlyField()
    total_culls = serializers.ReadOnlyField()
    cull_percentage = serializers.ReadOnlyField()
    reconciliation = serializers.ReadOnlyField()
    weight_vs_standard = serializers.ReadOnlyField()
    scorecard = serializers.ReadOnlyField()
    water_alerts = serializers.ReadOnlyField()
    feed_reconciliation = serializers.ReadOnlyField()
    live_birds = serializers.ReadOnlyField()
    fcr = serializers.ReadOnlyField()
    epef = serializers.ReadOnlyField()
    avg_sold_weight_kg = serializers.ReadOnlyField()
    total_medication_cost = serializers.ReadOnlyField()
    daily_entries = DailyEntrySerializer(many=True, read_only=True)
    sales = SaleSerializer(many=True, read_only=True)
    medications = MedicationSerializer(many=True, read_only=True)
    farm_name = serializers.CharField(source='farm.name', read_only=True)

    class Meta:
        model = Flock
        fields = '__all__'
        list_serializer_class = PrimedFlockList


class FlockListSerializer(PrimedFlocks, ChickQualityFields, serializers.ModelSerializer):
    age_days = serializers.ReadOnlyField()
    total_mortality = serializers.ReadOnlyField()
    total_feed_kg = serializers.ReadOnlyField()
    feed_by_type = serializers.ReadOnlyField()
    feed_schedule_status = serializers.ReadOnlyField()
    total_sold_birds = serializers.ReadOnlyField()
    total_sold_weight_kg = serializers.ReadOnlyField()
    mortality_percentage = serializers.ReadOnlyField()
    livability_percentage = serializers.ReadOnlyField()
    total_culls = serializers.ReadOnlyField()
    cull_percentage = serializers.ReadOnlyField()
    reconciliation = serializers.ReadOnlyField()
    weight_vs_standard = serializers.ReadOnlyField()
    scorecard = serializers.ReadOnlyField()
    water_alerts = serializers.ReadOnlyField()
    feed_reconciliation = serializers.ReadOnlyField()
    live_birds = serializers.ReadOnlyField()
    fcr = serializers.ReadOnlyField()
    epef = serializers.ReadOnlyField()
    avg_sold_weight_kg = serializers.ReadOnlyField()
    total_medication_cost = serializers.ReadOnlyField()
    flock_feed_stock = serializers.ReadOnlyField()
    farm_name = serializers.CharField(source='farm.name', read_only=True)
    supervisor_name = serializers.SerializerMethodField()

    class Meta:
        model = Flock
        fields = '__all__'
        list_serializer_class = PrimedFlockList

    def get_supervisor_name(self, obj):
        if obj.supervisor:
            return f"{obj.supervisor.first_name} {obj.supervisor.last_name}".strip() or obj.supervisor.username
        return None


class FarmNameSerializer(serializers.ModelSerializer):
    """What the feed mill needs to know about a farm: which one it is."""
    class Meta:
        model = Farm
        fields = ['id', 'farm_code', 'name', 'region']
        read_only_fields = fields


class PrimedFarmList(serializers.ListSerializer):
    """Page speed: fetch the flocks (and supervisors) of all listed farms at once."""

    def to_representation(self, data):
        farms = list(data.all() if hasattr(data, 'all') else data)
        if farms:
            from django.db.models import prefetch_related_objects
            by_farm = {f.pk: {'active': [], 'closed': []} for f in farms}
            flocks = list(Flock.objects.filter(farm_id__in=by_farm, status__in=('active', 'closed'))
                          .select_related('farm', 'supervisor').order_by('id'))
            for fl in flocks:
                by_farm[fl.farm_id][fl.status].append(fl)
            prefetch_related_objects(farms, 'assigned_supervisors__user')
            prime_flocks(flocks)
            for f in farms:
                f._flocks_by_status = by_farm[f.pk]
        else:
            flocks = []
        try:
            return super().to_representation(farms)
        finally:
            unprime(flocks)
            for f in farms:
                f._flocks_by_status = None


class FarmSerializer(serializers.ModelSerializer):
    active_flocks = serializers.SerializerMethodField()

    def validate_farm_code(self, value):
        # E14: unique among live farms (a deleted farm's code may be reused).
        qs = Farm.objects.filter(farm_code=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f'Farm code {value} is already in use.')
        return value
    closed_flocks = serializers.SerializerMethodField()
    supervisor_names = serializers.SerializerMethodField()
    has_valid_pan = serializers.ReadOnlyField()
    tds_rate_pct = serializers.ReadOnlyField()

    class Meta:
        model = Farm
        fields = '__all__'
        list_serializer_class = PrimedFarmList

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        profile = getattr(user, 'profile', None)
        if user is not None and not (profile.is_admin if profile is not None else user.is_superuser):
            attrs.pop('pan', None)      # PAN is admin-only: a supervisor's save can't change or clear it
        return attrs

    def validate_pan(self, value):
        import re
        if value:
            value = value.strip().upper()
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', value):
                raise serializers.ValidationError(
                    'PAN must be 10 characters: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F).'
                )
        return value

    def _flocks(self, obj, status):
        cached = getattr(obj, '_flocks_by_status', None)
        if cached is not None:
            return cached[status]
        return obj.flocks.filter(status=status).select_related('farm', 'supervisor')

    def get_active_flocks(self, obj):
        return FlockListSerializer(self._flocks(obj, 'active'), many=True).data

    def get_closed_flocks(self, obj):
        return FlockListSerializer(self._flocks(obj, 'closed'), many=True).data

    def get_supervisor_names(self, obj):
        if getattr(obj, '_flocks_by_status', None) is not None:      # list page: prefetched
            supervisors = [p for p in obj.assigned_supervisors.all() if p.role == 'supervisor']
        else:
            supervisors = obj.assigned_supervisors.filter(role='supervisor').select_related('user')
        return ', '.join(
            f"{s.user.first_name} {s.user.last_name}".strip() or s.user.username
            for s in supervisors
        ) or None


class FeedOrderSerializer(serializers.ModelSerializer):
    farm_name = serializers.CharField(source='farm.name', read_only=True)
    farm_code = serializers.CharField(source='farm.farm_code', read_only=True)
    flock_info = serializers.SerializerMethodField()
    ordered_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FeedOrder
        fields = '__all__'

    def get_ordered_by_name(self, obj):
        if obj.ordered_by:
            return f"{obj.ordered_by.first_name} {obj.ordered_by.last_name}".strip() or obj.ordered_by.username
        return ''

    def get_flock_info(self, obj):
        if obj.flock:
            return f"Placed {obj.flock.placement_date} ({obj.flock.chick_count} chicks)"
        return None


class FeedTransferSerializer(serializers.ModelSerializer):
    from_farm_code = serializers.CharField(source='from_farm.farm_code', read_only=True)
    from_farm_name = serializers.CharField(source='from_farm.name', read_only=True)
    to_farm_code = serializers.CharField(source='to_farm.farm_code', read_only=True)
    to_farm_name = serializers.CharField(source='to_farm.name', read_only=True)
    transferred_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FeedTransfer
        fields = '__all__'

    def get_transferred_by_name(self, obj):
        if obj.transferred_by:
            return f"{obj.transferred_by.first_name} {obj.transferred_by.last_name}".strip() or obj.transferred_by.username
        return ''


class BillConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillConfig
        fields = '__all__'


class BillVersionSerializer(serializers.ModelSerializer):
    reopened_by_username = serializers.CharField(source='reopened_by.username', read_only=True, default=None)

    class Meta:
        model = BillVersion
        fields = ['id', 'flock', 'version', 'net_payable', 'amount_paid', 'generated_at',
                  'reopened_at', 'reopened_by', 'reopened_by_username', 'reason', 'data']
        read_only_fields = fields


class BillSerializer(serializers.ModelSerializer):
    farm_code = serializers.CharField(source='flock.farm.farm_code', read_only=True)
    farm_name = serializers.CharField(source='flock.farm.name', read_only=True)
    farmer_name = serializers.CharField(source='flock.farm.owner_name', read_only=True)
    placement_date = serializers.DateField(source='flock.placement_date', read_only=True)
    fcr = serializers.SerializerMethodField()
    avg_bird_weight_kg = serializers.SerializerMethodField()
    rate_card_name = serializers.SerializerMethodField()
    growing_method = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = '__all__'

    def get_rate_card_name(self, obj):
        return (obj.config_snapshot or {}).get('rate_card_name') or (obj.rate_card.label if obj.rate_card else None)

    def get_growing_method(self, obj):
        return (obj.config_snapshot or {}).get('growing_method') or 'margin_grade'

    def get_fcr(self, obj):
        if obj.total_sold_weight_kg and obj.total_sold_weight_kg > 0:
            return round(float(obj.total_feed_kg) / float(obj.total_sold_weight_kg), 3)
        return None

    def get_avg_bird_weight_kg(self, obj):
        if obj.total_sold_birds and obj.total_sold_birds > 0:
            return round(float(obj.total_sold_weight_kg) / obj.total_sold_birds, 3)
        return None


class DocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()
    doc_type_display = serializers.CharField(source='get_doc_type_display', read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'farm', 'flock', 'doc_type', 'doc_type_display', 'title',
            'file', 'file_url', 'original_name', 'notes',
            'uploaded_by', 'uploaded_by_name', 'uploaded_at',
        ]
        read_only_fields = ['uploaded_by', 'original_name']
        extra_kwargs = {'file': {'write_only': True}}

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get('request')
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_uploaded_by_name(self, obj):
        u = obj.uploaded_by
        if not u:
            return None
        return u.get_full_name() or u.username

    def validate(self, data):
        farm = data.get('farm')
        flock = data.get('flock')
        if not farm and not flock:
            raise serializers.ValidationError('A document must be attached to a farm or a flock.')
        return data


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'timestamp', 'actor', 'actor_username', 'action',
                  'model', 'object_id', 'object_repr', 'changes']
        read_only_fields = fields
