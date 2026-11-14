from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('api/accounting/', include('accounting.urls')),
    path('api/inventory/', include('inventory.urls')),
    path('api/chicken/', include('chicken_center.urls')),
    path('api/layer/', include('layer_farm.urls')),
]

# Serve uploaded media in development; nginx serves it in production.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
