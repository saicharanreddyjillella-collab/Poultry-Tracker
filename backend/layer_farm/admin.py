from django.contrib import admin
from .models import (LayerFarm, LayerFlock, FlockCost, Purchase, FeedBatch,
                     FeedToFlock, Application, DailyEntry, EggSale, Collection, Payment, Expense)
for m in (LayerFarm, LayerFlock, FlockCost, Purchase, FeedBatch, FeedToFlock,
          Application, DailyEntry, EggSale, Collection, Payment, Expense):
    admin.site.register(m)
