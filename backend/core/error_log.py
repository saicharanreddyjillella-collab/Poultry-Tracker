"""Keep ERROR log records in the database for the admin's System Health page.

Never raises and never logs from inside itself (a failing database must not turn
one error into a loop). Keeps the newest KEEP rows.
"""
import logging
import threading

KEEP = 500
_busy = threading.local()


class DatabaseErrorHandler(logging.Handler):
    def emit(self, record):
        if getattr(_busy, 'on', False) or record.name.startswith('django.db'):
            return
        _busy.on = True
        try:
            from django.apps import apps
            if not apps.ready:
                return
            from django.db import connection
            if connection.in_atomic_block and connection.needs_rollback:
                return                                       # the transaction is already broken
            from .models import ErrorEvent
            message = record.getMessage()
            if record.exc_info and record.exc_info[1] is not None:
                message += f' — {type(record.exc_info[1]).__name__}: {record.exc_info[1]}'
            request = getattr(record, 'request', None)
            path = getattr(request, 'path', '') or ''
            screen = record.name.endswith('client_errors')
            ErrorEvent.objects.create(level=record.levelname[:10], logger=record.name[:100],
                                      source='screen' if screen else 'server',
                                      message=message[:2000], path=path[:300])
            if ErrorEvent.objects.count() > KEEP + 50:          # prune now and then, not every time
                cutoff = ErrorEvent.objects.order_by('-timestamp').values_list('timestamp', flat=True)[KEEP - 1]
                ErrorEvent.objects.filter(timestamp__lt=cutoff).delete()
        except Exception:  # noqa: BLE001 — logging must never break the request
            pass
        finally:
            _busy.on = False
