from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('api/accounting/', include('accounting.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/chicken/', include('chicken_center.urls')),
    path('api/layer/', include('layer_farm.urls')),
]
