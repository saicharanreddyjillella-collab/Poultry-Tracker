"""Who can see which farms — one rule used by every endpoint.

  admin       all farms, everything
  supervisor  farms in their assigned regions, plus farms assigned to them
              directly; nothing from other regions (404, not 403, so ids of
              other regions' records aren't confirmed to exist)
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
    if is_admin(user) or is_plant(user):
        return Farm.objects.all()
    p = profile_of(user)
    if p is None:
        return Farm.objects.none()
    return Farm.objects.filter(
        Q(region__in=p.assigned_regions or []) | Q(assigned_supervisors=p)
    ).distinct()


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
