"""Page speed: load the totals behind Flock's figures for many flocks at once.

Each Flock figure (live birds, mortality, feed used, sales, medicine cost, feed
stock, weight vs standard, water alerts, …) normally runs its own query, so a
page listing N flocks ran 20–40 × N queries. `prime_flocks(flocks)` loads the
same data for all of them in a fixed number of queries and stores it on each
instance (`flock._stats`); the figures then read from memory.

A flock that has not been primed behaves exactly as before (fresh queries), so
code that writes and then re-reads a figure is unaffected. Serializers prime,
use, then `unprime` their instances.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum, prefetch_related_objects

FEED_FIELDS = (('BPSC', 'feed_bpsc_bags'), ('BSC', 'feed_bsc_bags'), ('BFP', 'feed_bfp_bags'))


def _sum(values):
    """Like SQL SUM: None when there is nothing to add."""
    values = list(values)
    return sum(values) if values else None


def prime_flocks(flocks):
    """Fill `_stats` on every flock that doesn't have it yet. Returns the list."""
    from .models import BillConfig, DailyEntry, FeedOrder, FeedTransfer, Medication, Sale
    flocks = list(flocks)
    todo = [f for f in flocks if getattr(f, '_stats', None) is None and f.pk]
    if not todo:
        return flocks
    ids = [f.pk for f in todo]

    entries = defaultdict(list)                                   # newest first, like the model's ordering
    for e in DailyEntry.objects.filter(flock_id__in=ids).order_by('flock_id', '-date'):
        entries[e.flock_id].append(e)
    sales = {r['flock_id']: r for r in Sale.objects.filter(flock_id__in=ids).values('flock_id')
             .annotate(birds=Sum('bird_count'), kg=Sum('total_weight_kg'))}
    meds = dict(Medication.objects.filter(flock_id__in=ids).values('flock_id').annotate(c=Sum('cost'))
                .values_list('flock_id', 'c'))
    delivered, t_in, t_out = defaultdict(dict), defaultdict(dict), defaultdict(dict)
    for r in FeedOrder.objects.filter(flock_id__in=ids, status='delivered').values('flock_id', 'feed_type') \
            .annotate(t=Sum('quantity_bags')):
        delivered[r['flock_id']][r['feed_type']] = int(r['t'])
    for r in FeedTransfer.objects.filter(to_flock_id__in=ids).values('to_flock_id', 'feed_type') \
            .annotate(t=Sum('quantity_bags')):
        t_in[r['to_flock_id']][r['feed_type']] = int(r['t'])
    for r in FeedTransfer.objects.filter(from_flock_id__in=ids).values('from_flock_id', 'feed_type') \
            .annotate(t=Sum('quantity_bags')):
        t_out[r['from_flock_id']][r['feed_type']] = int(r['t'])
    prefetch_related_objects(todo, 'bill')
    try:
        tolerance = float(BillConfig.get_active().feed_reconciliation_tolerance_pct)
    except Exception:
        tolerance = 5.0

    for f in todo:
        es = entries[f.pk]
        s = sales.get(f.pk, {})
        f._stats = {
            'entries': es,
            'mortality': _sum(e.mortality_count for e in es),
            'culls': _sum(e.cull_count for e in es),
            'consumed': {ft: _sum(getattr(e, field) for e in es) for ft, field in FEED_FIELDS},
            'latest_weighed': next((e for e in es if e.avg_body_weight_grams is not None), None),
            'sold_birds': s.get('birds'),
            'sold_kg': s.get('kg'),
            'med_cost': meds.get(f.pk),
            'delivered': delivered[f.pk], 't_in': t_in[f.pk], 't_out': t_out[f.pk],
            'tolerance': tolerance,
        }
    return flocks


def unprime(flocks):
    for f in flocks:
        if getattr(f, '_stats', None) is not None:
            f._stats = None


def zero(value):
    return value if value is not None else 0


__all__ = ['prime_flocks', 'unprime', 'Decimal']
