from django.contrib import admin
from .models import Unit, Item, StockMovement


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
