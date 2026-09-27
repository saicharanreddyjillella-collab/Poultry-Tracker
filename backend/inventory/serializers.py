from rest_framework import serializers
from .models import Unit, Item, StockMovement


class UnitSerializer(serializers.ModelSerializer):
    base_unit_symbol = serializers.CharField(source='base_unit.symbol', read_only=True, default=None)

    class Meta:
        model = Unit
        fields = ['id', 'name', 'symbol', 'base_unit', 'base_unit_symbol',
                  'factor_to_base', 'active']


class ItemSerializer(serializers.ModelSerializer):
    base_unit_symbol = serializers.CharField(source='base_unit.symbol', read_only=True)
    stock_on_hand = serializers.SerializerMethodField()

    class Meta:
        model = Item
        fields = ['id', 'name', 'kind', 'base_unit', 'base_unit_symbol',
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
