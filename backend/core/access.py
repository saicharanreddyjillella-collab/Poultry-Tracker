"""Who can see which farms — one rule used by every endpoint.

  admin       all farms, everything
  supervisor  every farm: any supervisor can see and enter data for any farm, so
              someone can cover when the responsible supervisor is on leave.
              Their regions (and directly assigned farms) are their "home": the
              default scope of the dashboard, reports and alerts (see scoped_farms).
  plant       feed mill: feed orders / transfers / stock / rates and the farm
              names those need — no flocks, daily data, bills, reports
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


def profile_of(user):
    return getattr(user, 'profile', None) if getattr(user, 'is_authenticated', False) else None


def is_admin(user):
    p = profile_of(user)
    if p is None:
        return bool(getattr(user, 'is_superuser', False))
    return p.is_admin


def is_plant(user):
    p = profile_of(user)
    return bool(p and p.is_plant)


def visible_farms(user):
    from .models import Farm
    if profile_of(user) is None and not is_admin(user):
        return Farm.objects.none()
    return Farm.objects.all()


def home_farms(user):
    """A supervisor's own farms (assigned regions + directly assigned); everything for admin/plant."""
    from .models import Farm
    p = profile_of(user)
    if is_admin(user) or is_plant(user) or p is None:
        return visible_farms(user)
    return Farm.objects.filter(
        Q(region__in=p.assigned_regions or []) | Q(assigned_supervisors=p)
    ).distinct()


def has_home(user):
    """True for a supervisor who has regions or farms of their own."""
    p = profile_of(user)
    return bool(p and not is_admin(user) and not is_plant(user)
                and (p.assigned_regions or p.assigned_farms.exists()))


def report_scope(request):
    """'mine' or 'all' for dashboards and reports: ?scope= wins; supervisors with
    their own regions default to 'mine', everyone else to 'all'."""
    asked = request.query_params.get('scope')
    if asked in ('mine', 'all'):
        return asked if has_home(request.user) else 'all'
    return 'mine' if has_home(request.user) else 'all'


def scoped_farms(request):
    return home_farms(request.user) if report_scope(request) == 'mine' else visible_farms(request.user)


def visible_farm_ids(user):
    return list(visible_farms(user).values_list('id', flat=True))


def get_visible_farm(user, farm_id):
    return get_object_or_404(visible_farms(user), pk=farm_id)


def get_visible_flock(user, flock_id):
    from .models import Flock
    return get_object_or_404(
        Flock.objects.select_related('farm').filter(farm_id__in=visible_farm_ids(user)), pk=flock_id)


def deny_plant(user):
    if is_plant(user):
        raise PermissionDenied('Feed-mill users can only use the Feed screens.')


class NotPlant(BasePermission):
    """Blocks the feed-mill role from farm/flock data, bills and reports."""
    message = 'Feed-mill users can only use the Feed screens.'

    def has_permission(self, request, view):
        return not is_plant(request.user)
