"""Document repository: files attached to a farm or a flock."""
from rest_framework import viewsets
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from ..models import Document
from ..serializers import DocumentSerializer
from ..permissions import CanAccessDocument


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    permission_classes = [CanAccessDocument]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = Document.objects.select_related('farm', 'flock', 'flock__farm', 'uploaded_by')
        farm_id = self.request.query_params.get('farm')
        flock_id = self.request.query_params.get('flock')
        if farm_id:
            qs = qs.filter(farm_id=farm_id)
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        # Supervisors see only documents for farms they can access.
        user = self.request.user
        profile = getattr(user, 'profile', None)
        if profile and not profile.is_admin:
            from ..models import Farm
            editable = [f.id for f in Farm.objects.all() if profile.can_edit_farm(f)]
            qs = qs.filter(farm_id__in=editable) | qs.filter(flock__farm_id__in=editable)
            qs = qs.distinct()
        return qs

    def perform_create(self, serializer):
        f = self.request.data.get('file')
        original = getattr(f, 'name', '') if f else ''
        serializer.save(uploaded_by=self.request.user, original_name=original)
