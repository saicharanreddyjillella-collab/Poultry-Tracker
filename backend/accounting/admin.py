from django.contrib import admin
from .models import Account, Party, Voucher, Entry, AuditLog


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


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'object_type', 'object_id')
    list_filter = ('action', 'object_type')
