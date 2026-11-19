"""Settings → Features: switch optional features on or off (admin)."""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..features import FEATURES, all_states
from ..models import FeatureSetting
from ..permissions import IsAdmin


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feature_states(request):
    """{key: true/false} — every signed-in screen uses this to show or hide features."""
    return Response(all_states())


def _row(key, states, saved):
    s = saved.get(key)
    by = s.updated_by if s else None
    return {'key': key, **{k: v for k, v in FEATURES[key].items() if k != 'default'},
            'enabled': states[key],
            'updated_at': s.updated_at if s else None,
            'updated_by': (by.get_full_name() or by.username) if by else None}


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def feature_settings(request):
    states = all_states()
    saved = {s.key: s for s in FeatureSetting.objects.select_related('updated_by')}
    return Response([_row(k, states, saved) for k in FEATURES])


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def feature_setting(request, key):
    if key not in FEATURES:
        raise NotFound('No such feature.')
    enabled = request.data.get('enabled')
    if not isinstance(enabled, bool):
        raise ValidationError({'enabled': 'Send true or false.'})
    s, _ = FeatureSetting.objects.get_or_create(key=key, defaults={'enabled': enabled, 'updated_by': request.user})
    s.enabled, s.updated_by = enabled, request.user
    s.save()
    saved = {x.key: x for x in FeatureSetting.objects.select_related('updated_by')}
    return Response(_row(key, all_states(), saved))
