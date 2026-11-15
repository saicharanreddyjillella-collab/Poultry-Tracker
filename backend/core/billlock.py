"""E5 — Settled-bill immutability.

Once a flock has a generated Bill, the bill and every settlement input under it
(the flock itself, daily entries, sales, medications, feed orders and feed
transfers) are locked. Any create/update/delete raises BillLocked (HTTP 409).

The only sanctioned way to change a settled flock is an admin "reopen" with a
reason: the bill is archived as a BillVersion, the flock goes back to active,
and closing it again generates the next version. Code that legitimately needs
to bypass the lock (the reopen itself) wraps the work in `unlocked()`.

Enforced with model signals so it holds for every entry point (API, admin,
shell), not just the views. Note: QuerySet.update() bypasses signals by design.
"""
import threading
from contextlib import contextmanager

from django.db.models.signals import pre_save, pre_delete
from django.dispatch import receiver
from rest_framework import status
from rest_framework.exceptions import APIException

_state = threading.local()

# Settlement inputs and the flock FK(s) that tie each one to a flock.
CHILD_FLOCK_FIELDS = {
    'DailyEntry': ('flock_id',),
    'Sale': ('flock_id',),
    'Medication': ('flock_id',),
    'FeedOrder': ('flock_id',),
    'FeedTransfer': ('from_flock_id', 'to_flock_id'),
}


class BillLocked(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = ('This flock has a generated bill and is locked. An admin must '
                      'reopen the bill (with a reason) before changes can be made.')
    default_code = 'bill_locked'


@contextmanager
def unlocked():
    """Temporarily allow changes to locked records (used by reopen)."""
    prev = getattr(_state, 'unlocked', False)
    _state.unlocked = True
    try:
        yield
    finally:
        _state.unlocked = prev


def _bypassed():
    return getattr(_state, 'unlocked', False)


def is_flock_locked(flock_id):
    if not flock_id:
        return False
    from .models import Bill
    return Bill.objects.filter(flock_id=flock_id).exists()


def assert_flock_unlocked(flock):
    """Views call this before their own validation so a user editing a billed
    flock is told it's locked, not some unrelated validation error."""
    fid = getattr(flock, 'pk', flock)
    if not _bypassed() and is_flock_locked(fid):
        raise _locked_error(fid)


def _locked_error(flock_id, what='changes'):
    return BillLocked(
        f'Flock #{flock_id} is closed and billed, so {what} are locked. '
        'An admin must reopen the bill (with a reason) first.'
    )


def _is_core(sender):
    return sender._meta.app_label == 'core'


def _linked_flock_ids(instance, fields):
    """Flock ids the row points at now AND before this save (moving a row
    off a billed flock is also a change to that flock's settlement)."""
    ids = {getattr(instance, f, None) for f in fields}
    if instance.pk:
        old = type(instance).objects.filter(pk=instance.pk).values_list(*fields).first()
        if old:
            ids.update(old)
    return {i for i in ids if i}


@receiver(pre_save)
def _guard_save(sender, instance, raw=False, **kwargs):
    if raw or _bypassed() or not _is_core(sender):
        return
    name = sender.__name__
    if name == 'Bill':
        if instance.pk:
            raise _locked_error(instance.flock_id, 'bill edits')
    elif name == 'Flock':
        if instance.pk and is_flock_locked(instance.pk):
            raise _locked_error(instance.pk, 'flock edits')
    elif name in CHILD_FLOCK_FIELDS:
        for fid in _linked_flock_ids(instance, CHILD_FLOCK_FIELDS[name]):
            if is_flock_locked(fid):
                raise _locked_error(fid, f'{name} changes')


@receiver(pre_delete)
def _guard_delete(sender, instance, **kwargs):
    if _bypassed() or not _is_core(sender):
        return
    name = sender.__name__
    if name == 'Bill':
        raise _locked_error(instance.flock_id, 'bill deletion')
    if name == 'BillVersion':
        raise BillLocked('Archived bill versions are permanent and cannot be deleted.')
    if name == 'Flock':
        from .models import BillVersion
        if is_flock_locked(instance.pk) or BillVersion.objects.filter(flock_id=instance.pk).exists():
            raise _locked_error(instance.pk, 'deleting the flock')
    elif name in CHILD_FLOCK_FIELDS:
        for f in CHILD_FLOCK_FIELDS[name]:
            fid = getattr(instance, f, None)
            if is_flock_locked(fid):
                raise _locked_error(fid, f'{name} deletion')
