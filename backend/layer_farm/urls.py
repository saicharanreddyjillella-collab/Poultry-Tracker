from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('farms', views.FarmViewSet)
router.register('flocks', views.FlockViewSet)
router.register('daily-entries', views.DailyEntryViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('flocks/<int:flock_id>/costs/', views.flock_costs),
    path('flocks/<int:flock_id>/summary/', views.flock_summary),
    path('dashboard/', views.dashboard),
    path('purchases/', views.purchases),
    path('feed-batches/', views.feed_batches),
    path('feed-to-flock/', views.feed_to_flock),
    path('applications/', views.applications),
    path('egg-sales/', views.egg_sales),
    path('collections/', views.collections),
    path('payments/', views.payments),
    path('expenses/', views.expenses),
    path('reverse/<str:kind>/<int:pk>/', views.reverse_entry),
]
