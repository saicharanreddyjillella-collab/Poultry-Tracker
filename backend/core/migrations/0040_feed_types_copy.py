"""Move feed figures from the fixed BPSC / BSC / BFP columns to configurable feed types.

Creates the three types (keys BPSC, BSC, BFP — permanent; the admin can rename the
codes later), copies every daily entry's bags into DailyEntryFeed lines and every
bag count into FeedStockCount.bags. The per-bird estimates that lived on each flock
(0.5 kg BPSC, 1.0 kg BSC by default) move onto the feed types.
"""
from django.db import migrations

TYPES = [
    # key, name, colour, order
    ('BPSC', 'Pre-Starter Crumble', '#1D4ED8', 1),
    ('BSC', 'Starter Crumble', '#0F766E', 2),
    ('BFP', 'Finisher Pellet', '#9A4A07', 3),
]
COLUMNS = {'BPSC': 'feed_bpsc_bags', 'BSC': 'feed_bsc_bags', 'BFP': 'feed_bfp_bags'}
COUNT_COLUMNS = {'BPSC': 'bpsc_bags', 'BSC': 'bsc_bags', 'BFP': 'bfp_bags'}


def _common_value(Flock, field, default):
    """The per-bird estimate most flocks used (they were set per flock before)."""
    from collections import Counter
    values = Counter(Flock.objects.values_list(field, flat=True))
    return values.most_common(1)[0][0] if values else default


def forward(apps, schema_editor):
    FeedType = apps.get_model('core', 'FeedType')
    DailyEntry = apps.get_model('core', 'DailyEntry')
    DailyEntryFeed = apps.get_model('core', 'DailyEntryFeed')
    FeedStockCount = apps.get_model('core', 'FeedStockCount')
    Flock = apps.get_model('core', 'Flock')
    per_bird = {'BPSC': _common_value(Flock, 'bpsc_per_bird_kg', 0.5),
                'BSC': _common_value(Flock, 'bsc_per_bird_kg', 1.0), 'BFP': None}
    for key, name, colour, order in TYPES:
        FeedType.objects.get_or_create(key=key, defaults={'code': key, 'name': name, 'colour': colour,
                                                          'sort_order': order, 'per_bird_kg': per_bird[key]})
    manager = getattr(DailyEntry, 'all_objects', DailyEntry.objects)
    have = set(DailyEntryFeed.objects.values_list('entry_id', 'feed_type'))      # safe to run twice
    lines = []
    for row in manager.values('id', *COLUMNS.values()):
        for key, col in COLUMNS.items():
            if row[col] and (row['id'], key) not in have:
                lines.append(DailyEntryFeed(entry_id=row['id'], feed_type=key, bags=row[col]))
    DailyEntryFeed.objects.bulk_create(lines, batch_size=2000)
    for c in FeedStockCount.objects.all():
        c.bags = {key: getattr(c, col) for key, col in COUNT_COLUMNS.items() if getattr(c, col)}
        c.save(update_fields=['bags'])


def backward(apps, schema_editor):
    DailyEntry = apps.get_model('core', 'DailyEntry')
    DailyEntryFeed = apps.get_model('core', 'DailyEntryFeed')
    FeedStockCount = apps.get_model('core', 'FeedStockCount')
    manager = getattr(DailyEntry, 'all_objects', DailyEntry.objects)
    for line in DailyEntryFeed.objects.filter(feed_type__in=COLUMNS):
        manager.filter(pk=line.entry_id).update(**{COLUMNS[line.feed_type]: line.bags})
    DailyEntryFeed.objects.all().delete()        # the columns hold the figures again
    for c in FeedStockCount.objects.all():
        for key, col in COUNT_COLUMNS.items():
            setattr(c, col, (c.bags or {}).get(key, 0))
        c.save()


class Migration(migrations.Migration):
    dependencies = [('core', '0039_feed_types_add')]
    operations = [migrations.RunPython(forward, backward)]
