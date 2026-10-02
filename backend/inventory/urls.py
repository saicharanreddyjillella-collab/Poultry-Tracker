from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('units', views.UnitViewSet)
router.register('stock-groups', views.StockGroupViewSet)
router.register('items', views.ItemViewSet)
router.register('movements', views.StockMovementViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('stock-on-hand/', views.stock_on_hand_view),
]
