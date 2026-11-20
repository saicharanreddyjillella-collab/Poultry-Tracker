"""Admin rules (Settings → Rules). Add one here and it appears on the Settings page.

`default` is used until the admin saves a value.
"""

SETTINGS = {
    'edit_window_days': {
        'name': 'Edit window (days)',
        'description': 'Supervisors can add, change or delete daily entries, sales and medicines dated within '
                       'this many days (today counts as day 1) on their own. Anything older is sent to an admin '
                       'for approval, with a reason. 0 = no limit.',
        'type': 'int', 'min': 0, 'max': 365, 'default': 3,
    },
}


def get(key):
    from .models import AppSetting
    spec = SETTINGS[key]
    row = AppSetting.objects.filter(key=key).values_list('value', flat=True).first()
    return spec['default'] if row is None else row


def all_values():
    from .models import AppSetting
    saved = dict(AppSetting.objects.filter(key__in=SETTINGS).values_list('key', 'value'))
    return {k: saved.get(k, spec['default']) for k, spec in SETTINGS.items()}


def clean(key, value):
    """Validate a value for `key`; returns the cleaned value or raises ValueError(message)."""
    spec = SETTINGS[key]
    if spec['type'] == 'int':
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValueError('Enter a whole number.')
        if not (spec['min'] <= v <= spec['max']):
            raise ValueError(f"Must be between {spec['min']} and {spec['max']}.")
        return v
    return value
