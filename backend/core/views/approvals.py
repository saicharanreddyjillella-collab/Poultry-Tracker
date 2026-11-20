"""Change requests (edits outside the edit window) — list, approve, reject."""
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..access import NotPlant, is_admin, visible_farm_ids
from ..models import ChangeRequest
from ..serializers import person


class ChangeRequestSerializer(serializers.ModelSerializer):
    model_label = serializers.CharField(source='get_model_display', read_only=True)
    action_label = serializers.CharField(source='get_action_display', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    farm_name = serializers.CharField(source='flock.farm.name', read_only=True)
    farm_id = serializers.IntegerField(source='flock.farm_id', read_only=True)
    requested_by_name = serializers.SerializerMethodField()
    decided_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ChangeRequest
        fields = '__all__'

    def get_requested_by_name(self, o):
        return person(o.requested_by)

    def get_decided_by_name(self, o):
        return person(o.decided_by)


@api_view(['GET'])
@permission_classes([IsAuthenticated, NotPlant])
def change_requests(request):
    """Admin: all; supervisors: requests on farms they can see. ?status=pending&flock=<id>"""
    qs = (ChangeRequest.objects.select_related('flock__farm', 'requested_by', 'decided_by')
          .filter(flock__farm_id__in=visible_farm_ids(request.user)))
    if request.query_params.get('status'):
        qs = qs.filter(status=request.query_params['status'])
    if request.query_params.get('flock'):
        qs = qs.filter(flock_id=request.query_params['flock'])
    return Response(ChangeRequestSerializer(qs[:300], many=True).data)


def _pending(request, pk):
    if not is_admin(request.user):
        return None, Response({'error': 'Only an admin can approve or reject changes.'}, status=403)
    cr = ChangeRequest.objects.filter(pk=pk).select_related('flock__farm').first()
    if cr is None:
        return None, Response({'error': 'Not found'}, status=404)
    if cr.status != 'pending':
        return None, Response({'error': f'Already {cr.get_status_display().lower()}.'}, status=400)
    return cr, None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_change(request, pk):
    from ..edit_window import apply
    cr, err = _pending(request, pk)
    if err:
        return err
    try:
        cr.result_object_id = apply(cr, request.user)
    except ValidationError as e:
        return Response({'error': 'This change can no longer be applied as asked.', 'detail': e.detail}, status=400)
    except Exception as e:                                           # record gone, bill locked…
        detail = getattr(e, 'detail', None) or str(e)
        return Response({'error': 'This change can no longer be applied.', 'detail': detail}, status=400)
    cr.status, cr.decided_by, cr.decided_at = 'approved', request.user, timezone.now()
    cr.decision_note = (request.data.get('note') or '').strip()
    cr.save()
    return Response(ChangeRequestSerializer(cr).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_change(request, pk):
    cr, err = _pending(request, pk)
    if err:
        return err
    cr.status, cr.decided_by, cr.decided_at = 'rejected', request.user, timezone.now()
    cr.decision_note = (request.data.get('note') or '').strip()
    cr.save()
    return Response(ChangeRequestSerializer(cr).data)
