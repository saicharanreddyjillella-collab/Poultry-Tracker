from django.contrib import admin
from .models import Farm, Flock, DailyEntry, Sale, FeedRate, Medication

@admin.register(Farm)
class FarmAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner_name', 'location', 'house_count')

@admin.register(Flock)
class FlockAdmin(admin.ModelAdmin):
    list_display = ('farm', 'breed', 'placement_date', 'chick_count', 'status')

@admin.register(DailyEntry)
class DailyEntryAdmin(admin.ModelAdmin):
    list_display = ('flock', 'date', 'mortality_count', 'feed_consumed_kg')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('flock', 'date', 'bird_count', 'total_weight_kg', 'rate_per_kg')

@admin.register(FeedRate)
class FeedRateAdmin(admin.ModelAdmin):
    list_display = ('week_start_date', 'rate_per_kg')

@admin.register(Medication)
class MedicationAdmin(admin.ModelAdmin):
    list_display = ('flock', 'date', 'name', 'dose')
