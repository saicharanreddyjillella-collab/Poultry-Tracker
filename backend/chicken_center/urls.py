from django.urls import path
from . import views

urlpatterns = [
    path('sales/', views.sales),
    path('purchases/', views.purchases),
    path('collections/', views.collections),
    path('payments/', views.payments),
    path('expenses/', views.expenses),
    path('shrinkage/', views.shrinkage),
    path('pending-bills/', views.pending_bills),
    path('reverse/<str:kind>/<int:pk>/', views.reverse_entry),
]
