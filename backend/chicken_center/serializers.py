from rest_framework import serializers
from .models import Sale, Purchase, Collection, Payment, Expense, Shrinkage


class SaleSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = Sale
        fields = ['id', 'party', 'party_name', 'item', 'item_name', 'date',
                  'weight_kg', 'rate_per_kg', 'amount', 'note',
                  'whatsapp_status', 'created_at']
        read_only_fields = ['amount', 'whatsapp_status']


class PurchaseSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = Purchase
        fields = ['id', 'party', 'party_name', 'item', 'item_name', 'date',
                  'weight_kg', 'rate_per_kg', 'amount', 'note', 'created_at']
        read_only_fields = ['amount']


class CollectionSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)

    class Meta:
        model = Collection
        fields = ['id', 'party', 'party_name', 'date', 'amount', 'mode',
                  'note', 'whatsapp_status', 'created_at']
        read_only_fields = ['whatsapp_status']


class PaymentSerializer(serializers.ModelSerializer):
    party_name = serializers.CharField(source='party.name', read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'party', 'party_name', 'date', 'amount', 'mode',
                  'note', 'created_at']


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ['id', 'date', 'account_code', 'amount', 'mode', 'note', 'created_at']


class ShrinkageSerializer(serializers.ModelSerializer):
    item_name = serializers.CharField(source='item.name', read_only=True)

    class Meta:
        model = Shrinkage
        fields = ['id', 'item', 'item_name', 'date', 'weight_kg', 'value',
                  'reason', 'created_at']
