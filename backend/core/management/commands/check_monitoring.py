"""Send a test event to Sentry to confirm E7 monitoring is wired up.

    python manage.py check_monitoring
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Send a test message to Sentry (requires SENTRY_DSN).'

    def handle(self, *args, **options):
        if not getattr(settings, 'SENTRY_ENABLED', False):
            raise CommandError('Monitoring is off: set SENTRY_DSN in the environment and restart.')
        import sentry_sdk
        event_id = sentry_sdk.capture_message('Poultry-Tracker monitoring check', level='info')
        sentry_sdk.flush(timeout=10)
        self.stdout.write(self.style.SUCCESS(
            f'Test event sent (id {event_id}). Look for "Poultry-Tracker monitoring check" in Sentry.'))
