from rest_framework import serializers
from .models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication


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
    live_birds = serializers.ReadOnlyField()
    fcr = serializers.ReadOnlyField()
    daily_entries = DailyEntrySerializer(many=True, read_only=True)
    sales = SaleSerializer(many=True, read_only=True)
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
    live_birds = serializers.ReadOnlyField()
    fcr = serializers.ReadOnlyField()
    farm_name = serializers.CharField(source='farm.name', read_only=True)

    class Meta:
        model = Flock
        fields = '__all__'


class FarmSerializer(serializers.ModelSerializer):
    active_flocks = serializers.SerializerMethodField()
    closed_flocks = serializers.SerializerMethodField()

    class Meta:
        model = Farm
        fields = '__all__'

    def get_active_flocks(self, obj):
        flocks = obj.flocks.filter(status='active')
        return FlockListSerializer(flocks, many=True).data

    def get_closed_flocks(self, obj):
        flocks = obj.flocks.filter(status='closed')
        return FlockListSerializer(flocks, many=True).data
