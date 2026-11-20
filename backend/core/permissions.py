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
    """Farm details (owner, capacity, region…) and deleting a farm: admin, or a supervisor
    for farms in their own regions. Day-to-day data on any farm is open to every
    supervisor (see UserProfile.can_edit_farm)."""
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
            return request.user.profile.can_manage_farm(obj)
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


class CanAccessDocument(BasePermission):
    """Documents follow the owning farm's edit rights.

    Read: any authenticated user (list is filtered in the view).
    Write: admin, or a supervisor who can edit the owning farm.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if hasattr(request.user, 'profile') and request.user.profile.is_admin:
            return True
        # For create, resolve the owning farm from farm/flock in the payload.
        if request.method == 'POST':
            from .models import Farm, Flock
            farm_id = request.data.get('farm')
            flock_id = request.data.get('flock')
            farm = None
            if farm_id:
                farm = Farm.objects.filter(id=farm_id).first()
            elif flock_id:
                fl = Flock.objects.select_related('farm').filter(id=flock_id).first()
                farm = fl.farm if fl else None
            if farm and hasattr(request.user, 'profile'):
                return request.user.profile.can_edit_farm(farm)
            return False
        return True  # object-level check for update/delete

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if hasattr(request.user, 'profile') and request.user.profile.is_admin:
            return True
        farm = obj.owning_farm
        if farm and hasattr(request.user, 'profile'):
            return request.user.profile.can_edit_farm(farm)
        return False
