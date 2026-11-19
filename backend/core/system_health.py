"""System Health (admin): one page that says whether the system is in good shape.

Each check: {key, label, status: ok | warn | error | info, detail}.
"""
import datetime
import json
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.db.models import Count, Max, Q
from django.utils import timezone

BACKUP_OK_HOURS = 26          # daily backup + slack
BACKUP_ERROR_HOURS = 50       # two missed nights


def _check(key, label, status, detail):
    return {'key': key, 'label': label, 'status': status, 'detail': detail}


def database_check():
    try:
        with connection.cursor() as cur:
            if connection.vendor == 'postgresql':
                cur.execute('SELECT pg_database_size(current_database())')
                size = cur.fetchone()[0]
            else:
                cur.execute('SELECT 1')
                cur.fetchone()
                name = connection.settings_dict.get('NAME')
                size = os.path.getsize(name) if name and os.path.exists(str(name)) else None
        mb = f' · {size / 1024 / 1024:,.1f} MB' if size else ''
        return _check('database', 'Database', 'ok', f'Answering{mb}')
    except Exception as exc:  # noqa: BLE001
        return _check('database', 'Database', 'error', f'Not answering: {exc}')


def backup_check(now):
    path = getattr(settings, 'BACKUP_STATUS_FILE', '')
    if not path:
        return _check('backup', 'Backups', 'info',
                      'Not set up on this computer (automatic backups run on the server).')
    try:
        with open(path) as fh:
            status = json.load(fh)
    except FileNotFoundError:
        return _check('backup', 'Backups', 'error', 'No backup has run yet (no status file).')
    except Exception as exc:  # noqa: BLE001
        return _check('backup', 'Backups', 'error', f'Backup status unreadable: {exc}')
    try:
        when = datetime.datetime.fromisoformat(status['timestamp'])
    except (KeyError, ValueError):
        return _check('backup', 'Backups', 'error', 'Backup status has no valid time.')
    hours = (now - when).total_seconds() / 3600
    local = timezone.localtime(when).strftime('%d %b %H:%M')
    size = f" · {status['db_bytes'] / 1024 / 1024:,.1f} MB" if status.get('db_bytes') else ''
    off = ' · copied off-site' if status.get('offsite') not in (None, '', 'none', 'skipped') else ''
    if status.get('status') != 'ok':
        return _check('backup', 'Backups', 'error', f"Last backup FAILED ({local}): {status.get('message', '')}")
    if hours > BACKUP_ERROR_HOURS:
        return _check('backup', 'Backups', 'error', f'Last backup was {hours / 24:.1f} days ago ({local}).')
    if hours > BACKUP_OK_HOURS:
        return _check('backup', 'Backups', 'warn', f'Last backup was {hours:.0f} hours ago ({local}).')
    return _check('backup', 'Backups', 'ok', f'Last backup {local} ({hours:.0f} h ago){size}{off}')


def errors_check(now):
    from .models import ErrorEvent
    day = ErrorEvent.objects.filter(timestamp__gte=now - datetime.timedelta(hours=24))
    n = day.count()
    if not n:
        return _check('errors', 'Errors (24 h)', 'ok', 'None')
    screen = day.filter(source='screen').count()
    parts = [f'{n - screen} on the server'] if n - screen else []
    if screen:
        parts.append(f'{screen} on screens')
    return _check('errors', 'Errors (24 h)', 'warn', ', '.join(parts) + ' — see the list below.')


def entries_check(today):
    from .models import Flock
    yesterday = today - datetime.timedelta(days=1)
    missing = list(Flock.objects.filter(status='active', placement_date__lt=yesterday)
                   .exclude(daily_entries__date=yesterday).select_related('farm')
                   .order_by('farm__name').values_list('farm__name', flat=True))
    if not missing:
        return _check('entries', "Yesterday's daily entries", 'ok', 'Every active flock has one.')
    names = ', '.join(missing[:8]) + (f' and {len(missing) - 8} more' if len(missing) > 8 else '')
    return _check('entries', "Yesterday's daily entries", 'warn', f'Missing for {len(missing)}: {names}.')


def weather_check(today):
    from .heat import WeatherUnavailable, fetch_forecast
    from .models import RegionLocation
    loc = RegionLocation.objects.first()
    if loc is None:
        return _check('weather', 'Weather (Heat Stress)', 'info', 'No region locations set.')
    try:
        fetch_forecast(loc.latitude, loc.longitude, today)
        return _check('weather', 'Weather (Heat Stress)', 'ok', 'Forecast service reachable.')
    except WeatherUnavailable:
        return _check('weather', 'Weather (Heat Stress)', 'warn',
                      'Forecast service not reachable — Heat Stress shows no forecast until it is.')


def features_check():
    from .features import FEATURES, all_states
    states = all_states()
    on = [FEATURES[k]['name'] for k, v in states.items() if v]
    off = [FEATURES[k]['name'] for k, v in states.items() if not v]
    detail = f"On: {', '.join(on) or 'none'}" + (f" · Off: {', '.join(off)}" if off else '')
    return _check('features', 'Switchable features', 'info', detail)


def user_activity(now):
    from .models import AuditLog
    week = now - datetime.timedelta(days=7)
    acts = {r['actor_id']: r for r in AuditLog.objects.filter(actor__isnull=False).values('actor_id')
            .annotate(last=Max('timestamp'), week=Count('id', filter=Q(timestamp__gte=week)))}
    rows = []
    for u in User.objects.filter(is_active=True).select_related('profile').order_by('username'):
        profile = getattr(u, 'profile', None)
        a = acts.get(u.id, {})
        rows.append({'id': u.id, 'name': u.get_full_name() or u.username, 'username': u.username,
                     'role': profile.role if profile else ('admin' if u.is_superuser else ''),
                     'last_login': u.last_login, 'last_change': a.get('last'), 'changes_7d': a.get('week', 0)})
    rows.sort(key=lambda r: r['last_login'] or r['last_change'] or datetime.datetime.min.replace(
        tzinfo=datetime.timezone.utc), reverse=True)
    return rows


def health_report():
    from .models import ErrorEvent, Farm, Flock
    now = timezone.now()
    today = timezone.localdate()
    checks = [database_check(), backup_check(now), errors_check(now), entries_check(today),
              weather_check(today), features_check()]
    worst = 'error' if any(c['status'] == 'error' for c in checks) else \
        'warn' if any(c['status'] == 'warn' for c in checks) else 'ok'
    return {
        'as_of': now,
        'overall': worst,
        'checks': checks,
        'recent_errors': list(ErrorEvent.objects.values('id', 'timestamp', 'level', 'source', 'logger',
                                                        'message', 'path')[:20]),
        'users': user_activity(now),
        'counts': {'farms': Farm.objects.count(), 'active_flocks': Flock.objects.filter(status='active').count(),
                   'users': User.objects.filter(is_active=True).count()},
    }
