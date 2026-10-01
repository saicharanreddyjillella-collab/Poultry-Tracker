from rest_framework import serializers
from .models import (
    LayerFarm, LayerFlock, FlockCost, Purchase, FeedBatch, FeedBatchInput,
    FeedToFlock, Application, DailyEntry, EggSale, Collection, Payment, Expense,
)


class LayerFarmSerializer(serializers.ModelSerializer):
    class Meta:
        model = LayerFarm
        fields = ['id', 'name', 'code', 'location', 'active']


class LayerFlockSerializer(serializers.ModelSerializer):
    farm_name = serializers.CharField(source='farm.name', read_only=True)
    farm_code = serializers.CharField(source='farm.code', read_only=True)
    age_days = serializers.ReadOnlyField()
    live_birds = serializers.ReadOnlyField()
    total_mortality = serializers.ReadOnlyField()
    total_culls = serializers.ReadOnlyField()
    total_cost = serializers.ReadOnlyField()
    total_eggs = serializers.ReadOnlyField()
    eggs_sold = serializers.ReadOnlyField()
    egg_stock = serializers.ReadOnlyField()
    egg_revenue = serializers.ReadOnlyField()

    class Meta:
        model = LayerFlock
        fields = ['id', 'farm', 'farm_name', 'farm_code', 'name',
                  'placement_date', 'bird_count', 'status', 'age_days',
                  'live_birds', 'total_mortality', 'total_culls', 'total_cost',
                  'total_eggs', 'eggs_sold', 'egg_stock', 'egg_revenue']


class FlockCostSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlockCost
        fields = ['id', 'flock', 'date', 'category', 'amount', 'note']


class PurchaseSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True, default=None)
    is_reversed = serializers.BooleanField(source='voucher.is_reversed', read_only=True, default=False)

    class Meta:
        model = Purchase
        fields = ['id', 'vendor', 'vendor_name', 'kind', 'item', 'item_name',
                  'flock', 'date', 'qty', 'unit', 'rate', 'amount', 'note',
                  'is_reversed', 'created_at']
        read_only_fields = ['amount']


class FeedBatchInputSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = FeedBatchInput
        fields = ['id', 'item', 'item_name', 'qty_kg', 'cost']


class FeedBatchSerializer(serializers.ModelSerializer):
    feed_name = serializers.CharField(source='feed_item.name', read_only=True)
    inputs = FeedBatchInputSerializer(many=True, read_only=True)
    is_reversed = serializers.BooleanField(source='voucher.is_reversed', read_only=True, default=False)

    class Meta:
        model = FeedBatch
        fields = ['id', 'date', 'feed_item', 'feed_name', 'output_kg',
                  'materials_cost', 'overhead_cost', 'total_cost', 'cost_per_kg',
                  'note', 'inputs', 'is_reversed', 'created_at']
        read_only_fields = ['materials_cost', 'total_cost', 'cost_per_kg']


class FeedToFlockSerializer(serializers.ModelSerializer):
    flock_name = serializers.CharField(source='flock.name', read_only=True)
    feed_name = serializers.CharField(source='feed_item.name', read_only=True)

    class Meta:
        model = FeedToFlock
        fields = ['id', 'flock', 'flock_name', 'feed_item', 'feed_name', 'date',
                  'qty_kg', 'cost_per_kg', 'amount', 'note', 'created_at']
        read_only_fields = ['amount']


class ApplicationSerializer(serializers.ModelSerializer):
    flock_name = serializers.CharField(source='flock.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True, default=None)

    class Meta:
        model = Application
        fields = ['id', 'flock', 'flock_name', 'kind', 'item', 'item_name',
                  'date', 'qty', 'amount', 'note', 'created_at']


class DailyEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyEntry
        fields = ['id', 'flock', 'date', 'eggs', 'broken', 'feed_kg',
                  'mortality', 'culls', 'note', 'created_at']


class EggSaleSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)
    flock_name = serializers.CharField(source='flock.name', read_only=True)
    amount_due = serializers.ReadOnlyField()
    is_reversed = serializers.BooleanField(source='voucher.is_reversed', read_only=True, default=False)

    class Meta:
        model = EggSale
        fields = ['id', 'party', 'party_name', 'flock', 'flock_name', 'date',
                  'trays', 'rate_per_tray', 'amount', 'amount_received',
                  'amount_due', 'status', 'note', 'whatsapp_status',
                  'is_reversed', 'created_at']
        read_only_fields = ['amount', 'amount_received', 'status', 'whatsapp_status']


class CollectionSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)

    class Meta:
        model = Collection
        fields = ['id', 'party', 'party_name', 'date', 'amount', 'advance',
                  'mode', 'note', 'whatsapp_status', 'created_at']
        read_only_fields = ['advance', 'whatsapp_status']


class PaymentSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'party', 'party_name', 'date', 'amount', 'mode', 'note', 'created_at']


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ['id', 'date', 'account_code', 'amount', 'mode',
                  'split_across_flocks', 'note', 'created_at']
