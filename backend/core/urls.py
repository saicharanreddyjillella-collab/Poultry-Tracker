from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'farms', views.FarmViewSet)
router.register(r'flocks', views.FlockViewSet)
router.register(r'daily-entries', views.DailyEntryViewSet)
router.register(r'sales', views.SaleViewSet)
router.register(r'feed-rates', views.FeedRateViewSet)
router.register(r'medications', views.MedicationViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', views.dashboard),
    path('flocks/<int:flock_id>/cumulative/', views.flock_cumulative),
    path('farms/<int:farm_id>/cumulative/', views.farm_cumulative),
    path('reports/monthly/', views.monthly_report),
]
