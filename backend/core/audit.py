"""Automatic audit trail for money-affecting records.

Wired via signals in CoreConfig.ready(). Records create/update/delete with the
acting user (resolved from the current request — DRF sets request.user during
the view, which is before the save signals fire) and a field-level diff.
"""
from decimal import Decimal
import datetime
import uuid

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .middleware import get_current_request

# Models whose changes are audited. Keep this to records that affect money or
# settlement inputs; high-volume telemetry is deliberately excluded.
AUDITED_MODELS = (
    'Farm', 'Flock', 'Sale', 'DailyEntry', 'Medication',
    'FeedOrder', 'FeedTransfer', 'Bill', 'BillConfig', 'Document',
    'BillVersion', 'FeedStockCount', 'FeatureSetting', 'AppSetting', 'ChangeRequest', 'BillPayment',
    'FeedType', 'DailyEntryFeed',
)

# Fields never worth diffing.
SKIP_FIELDS = {'created_at', 'updated_at', 'generated_at', 'uploaded_at'}


def _jsonable(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (datetime.date, datetime.datetime)):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    if hasattr(v, 'pk'):          # FK instance
        return v.pk
    if hasattr(v, 'name') and hasattr(v, 'url'):  # FileField
        return v.name
    return v


def snapshot(instance):
    """Plain dict of the instance's concrete fields (FKs as ids)."""
    data = {}
    for f in instance._meta.concrete_fields:
        if f.name in SKIP_FIELDS:
            continue
        data[f.name] = _jsonable(getattr(instance, f.attname if f.is_relation else f.name))
    return data


def _actor():
    req = get_current_request()
    user = getattr(req, 'user', None) if req is not None else None
    if user is not None and getattr(user, 'is_authenticated', False):
        return user
    return None


def _record(action, instance, changes):
    from .models import AuditLog
    user = _actor()
    AuditLog.objects.create(
        actor=user,
        actor_username=getattr(user, 'username', '') or '',
        action=action,
        model=instance.__class__.__name__,
        object_id=str(instance.pk),
        object_repr=str(instance)[:200],
        changes=changes,
    )


def _is_audited(sender):
    return sender.__name__ in AUDITED_MODELS and sender._meta.app_label == 'core'


@receiver(pre_save)
def _capture_before(sender, instance, **kwargs):
    if not _is_audited(sender) or not instance.pk:
        return
    try:
        before = sender._base_manager.get(pk=instance.pk)   # sees soft-deleted rows too
        instance._audit_before = snapshot(before)
    except sender.DoesNotExist:
        instance._audit_before = None


@receiver(post_save)
def _on_save(sender, instance, created, **kwargs):
    if not _is_audited(sender):
        return
    after = snapshot(instance)
    if created:
        _record('create', instance, after)
        return
    before = getattr(instance, '_audit_before', None)
    if before is None:
        return
    diff = {k: [before.get(k), after.get(k)] for k in after if before.get(k) != after.get(k)}
    if not diff:
        return
    if 'deleted_at' in diff:                       # E14 soft delete / restore
        if after.get('deleted_at'):
            _record('delete', instance, {**after, '_soft': True})
        else:
            _record('restore', instance, diff)
        return
    _record('update', instance, diff)


@receiver(post_delete)
def _on_delete(sender, instance, **kwargs):
    if not _is_audited(sender):
        return
    _record('delete', instance, snapshot(instance))
