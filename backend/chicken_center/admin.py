from django.contrib import admin
from .models import Sale, Purchase, Collection, Payment, Expense, Shrinkage

for m in (Sale, Purchase, Collection, Payment, Expense, Shrinkage):
    admin.site.register(m)
