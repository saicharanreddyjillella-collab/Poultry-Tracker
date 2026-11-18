"""Heat-stress forecast: region map points (admin) + per-farm risk for the next days."""
from decimal import Decimal

from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..access import NotPlant, is_admin, visible_farms
from ..heat import heat_report
from ..models import Farm, Flock, RegionLocation


@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def heat_stress_report(request):
    """Admin: all farms. Supervisor: farms in their regions."""
    flocks = (Flock.objects.select_related('farm')
              .filter(status='active', farm__in=visible_farms(request.user)))
    return Response(heat_report(flocks, timezone.localdate()))


def _number(data, field, low, high):
    try:
        value = Decimal(str(data.get(field)))
    except Exception:
        raise ValidationError({field: 'Enter a number, e.g. 17.3850.'})
    if not (low <= value <= high):
        raise ValidationError({field: f'Must be between {low} and {high}.'})
    return value.quantize(Decimal('0.00001'))


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, NotPlant])
def region_locations(request):
    """GET: every farm region with its saved point (or null). POST {region, latitude, longitude}:
    set or change a region's point (admin only)."""
    if not is_admin(request.user):
        raise PermissionDenied('Only an admin can manage region locations.')
    if request.method == 'POST':
        region = (request.data.get('region') or '').strip()
        if not region:
            raise ValidationError({'region': 'Region is required.'})
        lat = _number(request.data, 'latitude', Decimal('-90'), Decimal('90'))
        lon = _number(request.data, 'longitude', Decimal('-180'), Decimal('180'))
        loc, _ = RegionLocation.objects.update_or_create(region=region, defaults={'latitude': lat, 'longitude': lon})
        return Response({'region': loc.region, 'latitude': str(loc.latitude), 'longitude': str(loc.longitude)})
    saved = {r.region: r for r in RegionLocation.objects.all()}
    regions = sorted(set(Farm.objects.exclude(region='').values_list('region', flat=True)) | set(saved))
    return Response([{'region': r,
                      'latitude': str(saved[r].latitude) if r in saved else None,
                      'longitude': str(saved[r].longitude) if r in saved else None} for r in regions])
