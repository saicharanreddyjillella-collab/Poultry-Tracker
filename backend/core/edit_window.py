"""Edit window for daily entries, sales and medicines.

Supervisors add / change / delete records dated within the window themselves.
Outside it, the request becomes a ChangeRequest (with a reason) that an admin
approves or rejects; approving applies it exactly as the supervisor asked, through
the same checks as a normal save. Admins are never limited.
"""
import datetime
from types import SimpleNamespace

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import app_settings
from .access import is_admin

REASON_FIELD = 'change_reason'


def window_days():
    return int(app_settings.get('edit_window_days') or 0)


def earliest_open_date(today=None):
    """First date a supervisor may still change on their own (None = no limit)."""
    n = window_days()
    if n <= 0:
        return None
    today = today or timezone.localdate()
    return today - datetime.timedelta(days=n - 1)


def _as_date(v):
    if v is None or v == '':
        return None
    if isinstance(v, datetime.date):
        return v
    try:
        return datetime.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _plain(data):
    """request.data → JSON-safe dict (no reason field)."""
    out = {}
    for k, v in (data.items() if hasattr(data, 'items') else []):
        if k == REASON_FIELD:
            continue
        out[k] = v if isinstance(v, (str, int, float, bool, type(None), list, dict)) else str(v)
    return out


def _snapshot(obj):
    from django.forms.models import model_to_dict
    snap = {k: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v)
            for k, v in model_to_dict(obj).items()}
    if hasattr(obj, 'feeds'):                       # daily entry: its feed by type
        snap['feed_bags'] = obj.feed_bags
    return snap


class EditWindowMixin:
    """For the entry / sale / medicine viewsets."""
    model_label = None            # 'DailyEntry' | 'Sale' | 'Medication'
    _approving = False            # set when an admin's approval applies a request

    def _outside(self, *dates):
        if self._approving or is_admin(self.request.user):
            return False
        first = earliest_open_date()
        return first is not None and any(d is not None and d < first for d in dates)

    def _queue(self, action, flock, record_date, payload, instance=None):
        from .models import ChangeRequest
        reason = (self.request.data.get(REASON_FIELD) or '').strip()
        if not reason:
            n = window_days()
            raise ValidationError({
                REASON_FIELD: f'{record_date:%d %b %Y} is outside the {n}-day edit window. Give a reason and '
                              f'it will go to an admin for approval.',
                'code': 'approval_needed',
            })
        cr = ChangeRequest.objects.create(
            model=self.model_label, action=action, object_id=instance.pk if instance else None,
            flock=flock, record_date=record_date, payload=payload,
            before=_snapshot(instance) if instance else {}, reason=reason, requested_by=self.request.user)
        return Response({'change_request': cr.pk, 'status': 'pending',
                         'message': 'Sent to an admin for approval. Nothing changes until it is approved.'},
                        status=status.HTTP_202_ACCEPTED)

    def create(self, request, *args, **kwargs):
        d = _as_date(request.data.get('date'))
        if self._outside(d):
            ser = self.get_serializer(data=_plain(request.data))
            ser.is_valid(raise_exception=True)                          # show mistakes now, not at approval
            return self._queue('create', ser.validated_data['flock'], d, _plain(request.data))
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        new = _as_date(request.data.get('date')) or instance.date
        if self._outside(instance.date, new):
            ser = self.get_serializer(instance, data=_plain(request.data), partial=kwargs.get('partial', False))
            ser.is_valid(raise_exception=True)
            return self._queue('update', instance.flock, min(instance.date, new), _plain(request.data), instance)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if self._outside(instance.date):
            return self._queue('delete', instance.flock, instance.date, {}, instance)
        return super().destroy(request, *args, **kwargs)


def viewset_for(model_label):
    from .views.data import DailyEntryViewSet, MedicationViewSet, SaleViewSet
    return {'DailyEntry': DailyEntryViewSet, 'Sale': SaleViewSet, 'Medication': MedicationViewSet}[model_label]


@transaction.atomic
def apply(cr, admin):
    """Carry out an approved request as the supervisor who asked (all normal checks apply)."""
    View = viewset_for(cr.model)
    view = View()
    view._approving = True
    view.format_kwarg = None
    view.kwargs = {}
    view.request = SimpleNamespace(user=cr.requested_by or admin, data=cr.payload, query_params={},
                                   method='POST')
    Model = View.queryset.model
    if cr.action == 'create':
        view.action = 'create'
        ser = view.get_serializer(data=cr.payload)
        ser.is_valid(raise_exception=True)
        view.perform_create(ser)
        return ser.instance.pk
    instance = Model.objects.get(pk=cr.object_id)
    if cr.action == 'update':
        view.action = 'partial_update'
        ser = view.get_serializer(instance, data=cr.payload, partial=True)
        ser.is_valid(raise_exception=True)
        view.perform_update(ser)
        return instance.pk
    view.action = 'destroy'
    view.perform_destroy(instance)
    return instance.pk
