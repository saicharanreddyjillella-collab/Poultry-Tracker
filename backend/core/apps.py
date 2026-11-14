from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        # Register audit-trail signal handlers.
        from . import audit  # noqa: F401
