from django.contrib import admin
from .models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication, UserProfile, FeedOrder, FeedTransfer, BillConfig, Bill

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone')
    filter_horizontal = ('assigned_farms',)

@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ('farm_code', 'name', 'owner_name', 'shed_type', 'region', 'location', 'capacity')

@admin.register(Flock)
class FlockAdmin(admin.ModelAdmin):
    list_display = ('farm', 'placement_date', 'chick_count', 'status', 'bpsc_per_bird_kg', 'bsc_per_bird_kg')

@admin.register(DailyEntry)
class DailyEntryAdmin(admin.ModelAdmin):
    list_display = ('flock', 'date', 'mortality_count', 'feed_bpsc_bags', 'feed_bsc_bags', 'feed_bfp_bags')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('flock', 'date', 'bird_count', 'total_weight_kg', 'rate_per_kg')

@admin.register(FeedRate)
class FeedRateAdmin(admin.ModelAdmin):
    list_display = ('week_start_date', 'feed_type', 'rate_per_kg')

@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('flock', 'date', 'name', 'dose')

@admin.register(FeedOrder)
class FeedOrderAdmin(admin.ModelAdmin):
    list_display = ('farm', 'feed_type', 'quantity_bags', 'status', 'ordered_by', 'order_date')

@admin.register(BillConfig)
class BillConfigAdmin(admin.ModelAdmin):
    list_display = ('chick_cost_per_bird', 'feed_cost_per_kg', 'admin_cost_per_chick', 'is_active')

@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    """Read-only: settled bills are locked (E5). Reopen via the API/UI with a reason."""
    list_display = ('flock', 'version', 'farmer_grade', 'production_cost_per_kg', 'net_payable', 'generated_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from .models import BillVersion  # noqa: E402


@admin.register(BillVersion)
class BillVersionAdmin(admin.ModelAdmin):
    list_display = ('flock', 'version', 'net_payable', 'reopened_by', 'reopened_at')
    readonly_fields = [f.name for f in BillVersion._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


from .models import AuditLog  # noqa: E402


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'actor_username', 'action', 'model', 'object_id', 'object_repr')
    list_filter = ('action', 'model')
    search_fields = ('actor_username', 'object_id', 'object_repr')
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
