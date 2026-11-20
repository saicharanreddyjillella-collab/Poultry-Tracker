"""Feed types (Settings → Feed types): the live list, lookups and per-type sums.

Everything that stores a feed type stores its permanent `key`; screens show `code`.
"""
BAG_KG = 50


DEFAULTS = [
    # key/code, name, colour, order, kg per bird (None = the rest)
    ('BPSC', 'Pre-Starter Crumble', '#1D4ED8', 1, '0.5'),
    ('BSC', 'Starter Crumble', '#0F766E', 2, '1.0'),
    ('BFP', 'Finisher Pellet', '#9A4A07', 3, None),
]


def ensure_defaults():
    """Create the standard three feed types when none exist (fresh database, test data)."""
    from decimal import Decimal
    from .models import FeedType
    if FeedType.objects.exists():
        return
    for key, name, colour, order, kg in DEFAULTS:
        FeedType.objects.create(key=key, code=key, name=name, colour=colour, sort_order=order,
                                per_bird_kg=Decimal(kg) if kg else None)


def all_types():
    """Every feed type, in feeding order (retired ones included — old records use them)."""
    from .models import FeedType
    types = list(FeedType.objects.all())
    if not types:
        ensure_defaults()
        types = list(FeedType.objects.all())
    return types


def active_keys():
    from .models import FeedType
    return list(FeedType.objects.filter(active=True).values_list('key', flat=True))


def keys():
    return [t.key for t in all_types()]


def codes():
    """{key: code} for showing a stored key."""
    return {t.key: t.code for t in all_types()}


def zero():
    return {k: 0 for k in keys()}


def add(a, b, sign=1):
    """Per-type sum of two {key: bags} dicts."""
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = out.get(k, 0) + sign * (v or 0)
    return out


def total(bags):
    return sum((v or 0) for v in (bags or {}).values())


def consumed_by_flock(flock_ids, until=None, on=None):
    """{flock_id: {key: bags}} eaten per flock (optionally up to / on a date)."""
    from django.db.models import Sum
    from .models import DailyEntryFeed
    qs = DailyEntryFeed.objects.filter(entry__flock_id__in=flock_ids, entry__deleted_at__isnull=True)
    if until is not None:
        qs = qs.filter(entry__date__lte=until)
    if on is not None:
        qs = qs.filter(entry__date=on)
    out = {}
    for r in qs.values('entry__flock_id', 'feed_type').annotate(t=Sum('bags')):
        out.setdefault(r['entry__flock_id'], {})[r['feed_type']] = int(r['t'] or 0)
    return out


def consumed_in(entries_qs):
    """{key: bags} eaten across a DailyEntry queryset."""
    from django.db.models import Sum
    from .models import DailyEntryFeed
    rows = (DailyEntryFeed.objects.filter(entry__in=entries_qs)
            .values('feed_type').annotate(t=Sum('bags')))
    return {r['feed_type']: int(r['t'] or 0) for r in rows}


def budget_kg_per_bird(types=None):
    """[(key, kg per bird or None)] in feeding order, active types only — None = the rest.
    Pass `types` (a list already loaded) to avoid a query per call."""
    return [(t.key, float(t.per_bird_kg) if t.per_bird_kg is not None else None)
            for t in (types if types is not None else all_types()) if t.active]


def split_by_budget(kg_per_bird_eaten_before, kg_per_bird_now, types=None):
    """Split feed eaten between two points of a bird's life across the feed types, by
    their per-bird budgets in feeding order (the last type without a budget takes the
    rest). Returns {key: kg per bird}. Used for forecasting — no ages involved."""
    out, start, edge = {}, kg_per_bird_eaten_before, 0.0
    end = kg_per_bird_now
    budget = budget_kg_per_bird(types)
    for i, (key, kg) in enumerate(budget):
        last = i == len(budget) - 1
        hi = float('inf') if (kg is None or last) else edge + kg
        part = max(0.0, min(end, hi) - max(start, edge))
        if part:
            out[key] = out.get(key, 0.0) + part
        if hi == float('inf'):
            break
        edge = hi
    return out


def current_type(consumed, chicks, types=None):
    """The feed a flock is on now: the first type (in order) whose per-bird budget isn't
    used up yet; the last type once all budgets are used."""
    budget = budget_kg_per_bird(types)
    if not budget:
        return None
    for key, kg in budget:
        if kg is None:
            return key
        if (consumed.get(key, 0) or 0) * BAG_KG < kg * chicks:
            return key
    return budget[-1][0]


def finisher_key():
    """The last active feed in feeding order (what birds eat near lifting)."""
    from .models import FeedType
    t = FeedType.objects.filter(active=True).order_by('-sort_order', '-id').first()
    return t.key if t else None
