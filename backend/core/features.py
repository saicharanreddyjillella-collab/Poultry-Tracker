"""Switchable features (admin: Settings → Features).

Add a feature here and it appears on the Settings page with an on/off switch.
`default` is used until the admin changes it. Turning a feature off hides its
screens and blocks its API; data already saved is kept.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

FEATURES = {
    'feed_audit': {
        'name': 'Feed Audit (bag counts)',
        'description': "Supervisors record feed bag counts on each flock, and the admin's Feed Audit flags missing "
                       "bags, feeding above the age standard and feed left at close.",
        'when_off': 'Bag counts and the Feed Audit page are hidden. Counts already saved are kept.',
        'default': True,
    },
    'lift_planner': {
        'name': 'Best Day to Lift',
        'description': 'Daily live-bird market rate and the lift planner: sell each flock now or hold, '
                       'and how much it is worth.',
        'when_off': 'The Best Day to Lift page is hidden. Market rates already saved are kept.',
        'default': True,
    },
    'placement_planner': {
        'name': 'Who Gets the Next Chicks',
        'description': 'Ranks growers on their settled flocks (feed efficiency, mortality, consistency) and '
                       'plans which free farms get the next chicks.',
        'when_off': 'The grower ranking page is hidden. Nothing is stored by this feature.',
        'default': True,
    },
}


def all_states():
    from .models import FeatureSetting
    saved = dict(FeatureSetting.objects.filter(key__in=FEATURES).values_list('key', 'enabled'))
    return {key: saved.get(key, spec['default']) for key, spec in FEATURES.items()}


def is_enabled(key):
    from .models import FeatureSetting
    row = FeatureSetting.objects.filter(key=key).values_list('enabled', flat=True).first()
    return FEATURES[key]['default'] if row is None else row


class FeatureOff(PermissionDenied):
    default_code = 'feature_off'


def feature_required(key):
    """Permission class: refuse when the feature is switched off."""
    class FeatureOn(BasePermission):
        def has_permission(self, request, view):
            if not is_enabled(key):
                raise FeatureOff(f"{FEATURES[key]['name']} is turned off. An admin can turn it on in "
                                 f"Settings → Features.")
            return True
    FeatureOn.__name__ = f'FeatureOn_{key}'
    return FeatureOn
