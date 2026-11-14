"""Read-only audit trail API (admin only)."""
from rest_framework import viewsets
from rest_framework.permissions import BasePermission

from ..models import AuditLog
from ..serializers import AuditLogSerializer


class IsAdminProfile(BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and hasattr(request.user, 'profile')
                and request.user.profile.is_admin)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminProfile]

    def get_queryset(self):
        qs = AuditLog.objects.select_related('actor')
        p = self.request.query_params
        if p.get('model'):
            qs = qs.filter(model=p['model'])
        if p.get('object_id'):
            qs = qs.filter(object_id=p['object_id'])
        if p.get('actor'):
            qs = qs.filter(actor_username=p['actor'])
        if p.get('action'):
            qs = qs.filter(action=p['action'])
        limit = min(int(p.get('limit', 200)), 1000)
        return qs[:limit]
