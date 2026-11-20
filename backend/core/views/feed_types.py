"""Feed types (Settings → Feed types). Everyone signed in reads the list (every feed
screen needs it); only an admin adds, renames, reorders or retires a type."""
import re

from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response

from ..access import is_admin
from ..models import FeedType
from ..serializers import FeedTypeSerializer


class AdminWrites(BasePermission):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or is_admin(request.user)


def _new_key(code):
    """A permanent key from the first code: letters/digits only, unique."""
    base = re.sub(r'[^A-Z0-9]', '', code.upper())[:16] or 'FEED'
    key, n = base, 2
    while FeedType.objects.filter(key=key).exists():
        key, n = f'{base}{n}', n + 1
    return key


class FeedTypeViewSet(viewsets.ModelViewSet):
    queryset = FeedType.objects.all()
    serializer_class = FeedTypeSerializer
    permission_classes = [IsAuthenticated, AdminWrites]
    pagination_class = None

    def perform_create(self, serializer):
        last = FeedType.objects.order_by('-sort_order').first()
        order = serializer.validated_data.get('sort_order') or ((last.sort_order + 1) if last else 1)
        serializer.save(key=_new_key(serializer.validated_data['code']), sort_order=order)

    def destroy(self, request, *args, **kwargs):
        t = self.get_object()
        if FeedTypeSerializer().get_in_use(t):
            raise ValidationError({'error': f'{t.code} is on existing records, so it is kept. '
                                            f'Retire it instead (it then can\'t be chosen for new records).'})
        if FeedType.objects.filter(active=True).exclude(pk=t.pk).count() == 0:
            raise ValidationError({'error': 'Keep at least one feed type.'})
        return super().destroy(request, *args, **kwargs)

    def perform_update(self, serializer):
        t = serializer.instance
        if serializer.validated_data.get('active') is False and t.active and \
                not FeedType.objects.filter(active=True).exclude(pk=t.pk).exists():
            raise ValidationError({'active': 'Keep at least one active feed type.'})
        serializer.save()
