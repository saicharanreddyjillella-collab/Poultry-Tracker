"""E14 — Soft delete + restore.

Deleting a farm, flock, daily entry, sale, medication, feed order, feed
transfer or document no longer destroys it: the row is stamped deleted_at /
deleted_by and hidden from every normal query (the default manager and all
reverse relations exclude it). An admin can restore it from the Recycle Bin.

Cascades are soft too: deleting a farm also hides its flocks, feed orders and
documents; deleting a flock hides its entries, sales, medications and
documents. Everything removed by one action shares a `deletion_batch`, and
restore brings back exactly that batch — items deleted separately earlier stay
deleted.

Money trail (E5): records under a billed flock are locked, and a flock (or a
farm owning a flock) that has a bill or bill history can't be deleted at all.
"""
import uuid

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self, user=None):
        """Bulk delete is soft too (e.g. Django admin "delete selected")."""
        batch = uuid.uuid4()
        n = 0
        with transaction.atomic():
            for obj in self:
                obj.soft_delete(user=user, batch=batch)
                n += 1
        return n, {self.model._meta.label: n}

    delete.queryset_only = True

    def hard_delete(self):
        return super().delete()


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager: live rows only."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Live and deleted rows (Recycle Bin, restore, uniqueness checks)."""


class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True, editable=False)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, editable=False, related_name='+')
    deletion_batch = models.UUIDField(null=True, blank=True, db_index=True, editable=False)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    # Reverse relations whose live rows are soft-deleted along with this one.
    SOFT_DELETE_CHILDREN = ()

    class Meta:
        abstract = True

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def check_can_delete(self):
        """Override to forbid deletion (raise an APIException)."""

    def delete(self, using=None, keep_parents=False, user=None):
        self.soft_delete(user=user)
        return 1, {self._meta.label: 1}

    def soft_delete(self, user=None, batch=None, when=None):
        if self.deleted_at is not None:
            return
        with transaction.atomic():
            self.check_can_delete()
            batch = batch or uuid.uuid4()
            when = when or timezone.now()
            if user is None:                                    # API/admin: the request's user
                from .middleware import get_current_request
                req = get_current_request()
                user = getattr(req, 'user', None) if req is not None else None
            actor = user if getattr(user, 'is_authenticated', False) else None
            for rel in self.SOFT_DELETE_CHILDREN:
                for child in getattr(self, rel).all():          # live children only
                    child.soft_delete(user=actor, batch=batch, when=when)
            self.deleted_at, self.deleted_by, self.deletion_batch = when, actor, batch
            self.save(update_fields=['deleted_at', 'deleted_by', 'deletion_batch'])

    def hard_delete(self):
        return super().delete()

    def _restore(self):
        self.deleted_at = self.deleted_by = self.deletion_batch = None
        self.save(update_fields=['deleted_at', 'deleted_by', 'deletion_batch'])

    # Parents that must be live (or restored in the same batch) for a restore.
    def restore_parents(self):
        return []

    # Live rows that would clash with this one on restore → human message.
    def restore_conflict(self):
        return None


def soft_delete_models():
    from django.apps import apps
    return [m for m in apps.get_app_config('core').get_models() if issubclass(m, SoftDeleteModel)]


class RestoreError(Exception):
    pass


def batch_items(batch):
    items = []
    for model in soft_delete_models():
        items.extend(model.all_objects.filter(deletion_batch=batch))
    return items


def restore_batch(batch):
    """Restore everything deleted by one action. All-or-nothing."""
    items = batch_items(batch)
    if not items:
        raise RestoreError('Nothing to restore — this batch was already restored or does not exist.')
    in_batch = {(type(i), i.pk) for i in items}
    for item in items:
        for parent in item.restore_parents():
            if parent is not None and parent.is_deleted and (type(parent), parent.pk) not in in_batch:
                raise RestoreError(
                    f'{item._meta.verbose_name.title()} "{item}" belongs to {parent._meta.verbose_name} '
                    f'"{parent}", which is also deleted. Restore that first.')
        clash = item.restore_conflict()
        if clash:
            raise RestoreError(clash)
    with transaction.atomic():
        for item in items:
            item._restore()
    return items
