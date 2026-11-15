"""E12 — receive frontend crash reports from the React error boundary.

Logged at ERROR on `core.client_errors`, so they land in app.log and — when
SENTRY_DSN is set — in Sentry (E7). Open to anonymous users (the login page
can crash too) but throttled per IP, size-capped, and never echoes input.
"""
import logging

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

logger = logging.getLogger('core.client_errors')

LIMITS = {'message': 500, 'stack': 4000, 'component_stack': 4000,
          'path': 300, 'source': 40, 'release': 80}


def _clip(value, n):
    if value is None:
        return ''
    return str(value)[:n]


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def client_error(request):
    data = request.data if isinstance(request.data, dict) else {}
    report = {k: _clip(data.get(k), n) for k, n in LIMITS.items()}
    if not report['message']:
        return Response({'error': 'message is required'}, status=400)

    user = getattr(request, 'user', None)
    user_id = user.id if user is not None and user.is_authenticated else None
    logger.error(
        'Frontend error on %s: %s', report['path'] or '?', report['message'],
        extra={
            'client_source': report['source'],
            'client_stack': report['stack'],
            'client_component_stack': report['component_stack'],
            'client_release': report['release'],
            'client_user_id': user_id,
        },
    )
    return Response(status=204)


client_error.cls.throttle_scope = 'client_errors'
