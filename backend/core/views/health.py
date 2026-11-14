"""Liveness/readiness endpoint for load balancers and uptime monitors."""
import logging

from django.db import connection
from rest_framework.decorators import api_view, permission_classes, authentication_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger('core.health')


@api_view(['GET'])
@authentication_classes([])      # no JWT required
@permission_classes([AllowAny])
@throttle_classes([])            # never throttle health probes
def health(request):
    """Returns 200 {"status":"ok","db":"ok"} when the DB answers, else 503.
    Deliberately reveals nothing about versions, hosts or config."""
    checks = {}
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            cur.fetchone()
        checks['db'] = 'ok'
    except Exception as exc:  # noqa: BLE001 — any DB failure means unhealthy
        logger.error('health check: database unavailable: %s', exc)
        checks['db'] = 'error'

    healthy = all(v == 'ok' for v in checks.values())
    return Response({'status': 'ok' if healthy else 'degraded', **checks},
                    status=200 if healthy else 503)
