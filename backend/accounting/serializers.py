from rest_framework import serializers
from .models import Account, Party, Voucher, Entry


class AccountSerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = ['id', 'code', 'name', 'type', 'is_party_control',
                  'business', 'active', 'balance']

    def get_balance(self, obj):
        return obj.balance()


class PartySerializer(serializers.ModelSerializer):
    balance = serializers.SerializerMethodField()
    control_account_code = serializers.CharField(source='control_account.code', read_only=True)

    class Meta:
        model = Party
        fields = ['id', 'name', 'phone', 'address', 'party_type',
                  'control_account', 'control_account_code',
                  'business', 'active', 'balance']

    def get_balance(self, obj):
        return obj.balance()


class EntrySerializer(serializers.ModelSerializer):
    account_code = serializers.CharField(source='account.code', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True)
    party_name = serializers.CharField(source='party.name', read_only=True, default=None)

    class Meta:
        model = Entry
        fields = ['id', 'account', 'account_code', 'account_name',
                  'party', 'party_name', 'debit', 'credit']


class VoucherSerializer(serializers.ModelSerializer):
    entries = EntrySerializer(many=True, read_only=True)
    total_debit = serializers.ReadOnlyField()
    total_credit = serializers.ReadOnlyField()
    is_balanced = serializers.ReadOnlyField()

    class Meta:
        model = Voucher
        fields = ['id', 'date', 'type', 'narration', 'business',
                  'source_module', 'source_ref', 'created_at',
                  'is_reversed', 'reverses',
                  'total_debit', 'total_credit', 'is_balanced', 'entries']
