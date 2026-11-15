from rest_framework import serializers
from .models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication, FeedOrder, FeedTransfer, BillConfig, Bill, BillVersion, Document, AuditLog


class DailyEntrySerializer(serializers.ModelSerializer):
    total_feed_bags = serializers.ReadOnlyField()
    total_feed_kg = serializers.ReadOnlyField()
    feed_bpsc_kg = serializers.ReadOnlyField()
    feed_bsc_kg = serializers.ReadOnlyField()
    feed_bfp_kg = serializers.ReadOnlyField()

    class Meta:
        model = DailyEntry
        fields = '__all__'


class SaleSerializer(serializers.ModelSerializer):
    total_amount = serializers.ReadOnlyField()
    avg_bird_weight_kg = serializers.ReadOnlyField()

    class Meta:
        model = Sale
        fields = '__all__'


class FeedRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedRate
        fields = '__all__'


class MedicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medication
        fields = '__all__'


class FlockSerializer(serializers.ModelSerializer):
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


class FlockListSerializer(serializers.ModelSerializer):
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

    def get_supervisor_name(self, obj):
        if obj.supervisor:
            return f"{obj.supervisor.first_name} {obj.supervisor.last_name}".strip() or obj.supervisor.username
        return None


class FarmSerializer(serializers.ModelSerializer):
    active_flocks = serializers.SerializerMethodField()
    closed_flocks = serializers.SerializerMethodField()
    supervisor_names = serializers.SerializerMethodField()
    has_valid_pan = serializers.ReadOnlyField()
    tds_rate_pct = serializers.ReadOnlyField()

    class Meta:
        model = Farm
        fields = '__all__'

    def validate_pan(self, value):
        import re
        if value:
            value = value.strip().upper()
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]$', value):
                raise serializers.ValidationError(
                    'PAN must be 10 characters: 5 letters, 4 digits, 1 letter (e.g. ABCDE1234F).'
                )
        return value

    def get_active_flocks(self, obj):
        flocks = obj.flocks.filter(status='active')
        return FlockListSerializer(flocks, many=True).data

    def get_closed_flocks(self, obj):
        flocks = obj.flocks.filter(status='closed')
        return FlockListSerializer(flocks, many=True).data

    def get_supervisor_names(self, obj):
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

    class Meta:
        model = Bill
        fields = '__all__'

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
