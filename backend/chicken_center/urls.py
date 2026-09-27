from django.urls import path
from . import views
from . import exports

urlpatterns = [
    path('sales/', views.sales),
    path('purchases/', views.purchases),
    path('collections/', views.collections),
    path('payments/', views.payments),
    path('expenses/', views.expenses),
    path('shrinkage/', views.shrinkage),
    path('sales/<int:pk>/', views.sale_detail),
    path('pending-bills/', views.pending_bills),
    path('ageing/', views.ageing),
    path('export/pnl/', exports.export_pnl),
    path('export/cash-book/', exports.export_cash_book),
    path('export/pending-bills/', exports.export_pending_bills),
    path('export/ageing/', exports.export_ageing),
    path('reverse/<str:kind>/<int:pk>/', views.reverse_entry),
]
