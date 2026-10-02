from rest_framework import serializers
from .models import Unit, Item, StockMovement, StockGroup


class UnitSerializer(serializers.ModelSerializer):
    base_unit_symbol = serializers.CharField(source='base_unit.symbol', read_only=True, default=None)

    class Meta:
        model = Unit
        fields = ['id', 'name', 'symbol', 'base_unit', 'base_unit_symbol',
                  'factor_to_base', 'active']


class StockGroupSerializer(serializers.ModelSerializer):
    path = serializers.ReadOnlyField()
    under_name = serializers.CharField(source='under.name', read_only=True, default=None)

    class Meta:
        model = StockGroup
        fields = ['id', 'name', 'under', 'under_name', 'path', 'business',
                  'is_primary', 'active']
        read_only_fields = ['is_primary']


class ItemSerializer(serializers.ModelSerializer):
    base_unit_symbol = serializers.CharField(source='base_unit.symbol', read_only=True)
    stock_group_name = serializers.CharField(source='stock_group.name', read_only=True, default=None)
    stock_group_path = serializers.CharField(source='stock_group.path', read_only=True, default=None)
    stock_on_hand = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = ['id', 'name', 'kind', 'base_unit', 'base_unit_symbol',
                  'stock_group', 'stock_group_name', 'stock_group_path',
                  'rate_basis', 'business',
                  'sales_account', 'purchase_account', 'stock_account',
                  'active', 'stock_on_hand']

    def get_stock_on_hand(self, obj):
        return obj.stock_on_hand()


class StockMovementSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)
    entered_unit_symbol = serializers.CharField(source='entered_unit.symbol', read_only=True)

    class Meta:
        model = StockMovement
        fields = ['id', 'item', 'item_name', 'date', 'type',
                  'qty_in_base', 'qty_out_base', 'entered_qty',
                  'entered_unit', 'entered_unit_symbol', 'business',
                  'voucher', 'note', 'created_at']
