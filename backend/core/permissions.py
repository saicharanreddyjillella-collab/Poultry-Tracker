from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'profile') and
            request.user.profile.is_admin
        )


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return hasattr(request.user, 'profile') and request.user.profile.is_admin


class CanEditFarm(BasePermission):
    """Admin can edit any farm. Supervisor can edit only assigned farms."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if hasattr(request.user, 'profile') and request.user.profile.is_admin:
            return True
        return True  # object-level check below

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if hasattr(request.user, 'profile') and request.user.profile.is_admin:
            return True
        if hasattr(request.user, 'profile'):
            return request.user.profile.can_edit_farm(obj)
        return False


class CanEditFlock(BasePermission):
    """Check farm-level permission via the flock's farm."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return True  # will check at object level

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if hasattr(request.user, 'profile') and request.user.profile.is_admin:
            return True
        if hasattr(request.user, 'profile'):
            return request.user.profile.can_edit_farm(obj.farm)
        return False


class CanEditFlockData(BasePermission):
    """For daily entries, sales, medications — check flock's farm permission."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        # For create, check flock_id from request data
        if request.method == 'POST' and request.data.get('flock'):
            from .models import Flock
            try:
                flock = Flock.objects.select_related('farm').get(id=request.data['flock'])
                if hasattr(request.user, 'profile'):
                    return request.user.profile.can_edit_farm(flock.farm)
            except Flock.DoesNotExist:
                pass
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if hasattr(request.user, 'profile') and request.user.profile.is_admin:
            return True
        if hasattr(request.user, 'profile'):
            return request.user.profile.can_edit_farm(obj.flock.farm)
        return False
