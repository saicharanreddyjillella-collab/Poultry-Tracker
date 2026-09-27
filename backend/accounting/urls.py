from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('accounts', views.AccountViewSet)
router.register('parties', views.PartyViewSet)
router.register('vouchers', views.VoucherViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('reports/party/<int:party_id>/', views.party_statement),
    path('reports/account/<int:account_id>/', views.account_statement),
    path('reports/trial-balance/', views.trial_balance_view),
    path('reports/pnl/', views.profit_and_loss_view),
    path('reports/outstanding/', views.outstanding_view),
]
