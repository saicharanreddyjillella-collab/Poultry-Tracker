from django.contrib import admin
from .models import Account, Party, Voucher, Entry, Unit, Item, StockMovement, AuditLog


class EntryInline(admin.TabularInline):
    model = Entry
    extra = 0


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'type', 'is_party_control', 'business', 'active')
    list_filter = ('type', 'business', 'is_party_control', 'active')
    search_fields = ('code', 'name')


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ('name', 'party_type', 'phone', 'business', 'active')
    list_filter = ('party_type', 'business', 'active')
    search_fields = ('name', 'phone')


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'type', 'narration', 'business', 'total_debit', 'is_reversed')
    list_filter = ('type', 'business', 'is_reversed')
    search_fields = ('narration',)
    inlines = [EntryInline]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol', 'base_unit', 'factor_to_base', 'active')


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'base_unit', 'rate_basis', 'business', 'active')
    list_filter = ('kind', 'business', 'active')
    search_fields = ('name',)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('date', 'item', 'type', 'qty_in_base', 'qty_out_base', 'business')
    list_filter = ('type', 'business')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'object_type', 'object_id')
    list_filter = ('action', 'object_type')
