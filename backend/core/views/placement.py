"""Who gets the next chicks — grower ranking + placement plan (admin only)."""
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..features import feature_required
from ..models import Farm
from ..permissions import IsAdmin
from ..placement import placement_report


def _int(params, name, default, low, high):
    raw = params.get(name)
    if raw in (None, ''):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ValidationError({name: 'Enter a whole number.'})
    if not low <= value <= high:
        raise ValidationError({name: f'Must be between {low:,} and {high:,}.'})
    return value


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin, feature_required('placement_planner')])
def grower_ranking(request):
    """?chicks=30000 plans a placement; ?rest_days=14 (cleaning gap); ?region=… narrows it."""
    chicks = _int(request.query_params, 'chicks', 0, 0, 2_000_000)
    rest_days = _int(request.query_params, 'rest_days', 14, 0, 120)
    farms = Farm.objects.all()
    region = request.query_params.get('region')
    if region:
        farms = farms.filter(region=region)
    data = placement_report(farms, timezone.localdate(), chicks=chicks, rest_days=rest_days)
    data['regions'] = sorted(set(Farm.objects.exclude(region='').values_list('region', flat=True)))
    return Response(data)
