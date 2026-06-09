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
router.register(r'feed-orders', views.FeedOrderViewSet)
router.register(r'feed-transfers', views.FeedTransferViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('auth/login/', views.login_view),
    path('auth/me/', views.me_view),
    path('auth/change-password/', views.change_password),
    path('auth/users/', views.manage_users),
    path('auth/users/<int:user_id>/', views.manage_user_detail),
    path('auth/regions/', views.list_regions),
    path('dashboard/', views.dashboard),
    path('flocks/<int:flock_id>/cumulative/', views.flock_cumulative),
    path('farms/<int:farm_id>/cumulative/', views.farm_cumulative),
    path('reports/monthly/', views.monthly_report),
    path('reports/monthly/export/', views.export_monthly_report),
    path('reports/region/', views.region_performance),
    path('flocks/<int:flock_id>/export/', views.export_flock_report),
    path('feed-orders/<int:order_id>/mark-sent/', views.mark_order_sent),
    path('feed-orders/<int:order_id>/mark-delivered/', views.mark_order_delivered),
    path('feed-orders/<int:order_id>/cancel/', views.cancel_order),
    path('feed-stock/', views.feed_stock),
    path('bill-config/', views.bill_config_view),
    path('flocks/<int:flock_id>/close-and-bill/', views.close_flock_and_generate_bill),
    path('flocks/<int:flock_id>/bill/', views.get_bill),
    path('bills/', views.list_bills),
]
