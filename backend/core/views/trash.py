"""E14 — Recycle Bin: list soft-deleted items (grouped by delete action) and
restore them. Admin only."""
from collections import defaultdict

from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..softdelete import RestoreError, restore_batch, soft_delete_models

# Most significant first: the "headline" item of a delete action.
RANK = ['Farm', 'Flock', 'FeedOrder', 'FeedTransfer', 'DailyEntry', 'Sale', 'Medication', 'Document']
LABEL = {'Farm': 'Farm', 'Flock': 'Flock', 'FeedOrder': 'Feed order', 'FeedTransfer': 'Feed transfer',
         'DailyEntry': 'Daily entry', 'Sale': 'Sale', 'Medication': 'Medication', 'Document': 'Document'}
MAX_BATCHES = 200


def _label(obj):
    """Human label for the bin (model __str__ is often ambiguous)."""
    name = type(obj).__name__
    try:
        if name == 'Farm':
            return f'Farm {obj.farm_code} {obj.name}'
        if name == 'Flock':
            return f'Flock at {obj.farm.farm_code} {obj.farm.name}, placed {obj.placement_date:%d %b %Y}'
        flock = getattr(obj, 'flock', None)
        where = f'{flock.farm.farm_code} (flock placed {flock.placement_date:%d %b %Y})' if flock else ''
        if name == 'DailyEntry':
            return f'Entry for {obj.date:%d %b %Y} — {where}'
        if name == 'Sale':
            return f'Sale on {obj.date:%d %b %Y}, {obj.bird_count} birds — {where}'
        if name == 'Medication':
            return f'Medication {obj.name} on {obj.date:%d %b %Y} — {where}'
    except Exception:  # never let a label break the bin
        pass
    return f'{LABEL.get(name, name)}: {obj}'


def _admin_only(request):
    profile = getattr(request.user, 'profile', None)
    if not (profile and profile.is_admin):
        return Response({'error': 'Admin only'}, status=403)
    return None


@api_view(['GET'])
def trash_list(request):
    denied = _admin_only(request)
    if denied:
        return denied
    batches = defaultdict(lambda: {'items': defaultdict(list)})
    for model in soft_delete_models():
        rows = (model.all_objects.filter(deleted_at__isnull=False)
                .select_related('deleted_by').order_by('-deleted_at')[:2000])
        for obj in rows:
            b = batches[str(obj.deletion_batch)]
            b['deleted_at'] = max(b.get('deleted_at') or obj.deleted_at, obj.deleted_at)
            b['deleted_by'] = obj.deleted_by.username if obj.deleted_by else b.get('deleted_by')
            b['items'][model.__name__].append(obj)

    out = []
    for batch, b in batches.items():
        kinds = sorted(b['items'], key=lambda k: RANK.index(k) if k in RANK else 99)
        head_kind = kinds[0]
        heads = b['items'][head_kind]
        summary = (_label(heads[0]) if len(heads) == 1
                   else f'{len(heads)} {LABEL.get(head_kind, head_kind).lower()}s')
        also = {LABEL.get(k, k): len(b['items'][k]) for k in kinds[1:]}
        out.append({
            'batch': batch,
            'kind': head_kind,
            'summary': summary,
            'also_removed': also,
            'items_total': sum(len(v) for v in b['items'].values()),
            'deleted_at': b['deleted_at'],
            'deleted_by': b.get('deleted_by'),
        })
    out.sort(key=lambda x: x['deleted_at'], reverse=True)
    return Response(out[:MAX_BATCHES])


@api_view(['POST'])
def trash_restore(request, batch):
    denied = _admin_only(request)
    if denied:
        return denied
    try:
        items = restore_batch(batch)
    except RestoreError as e:
        return Response({'error': str(e)}, status=409)
    return Response({'restored': len(items)})
