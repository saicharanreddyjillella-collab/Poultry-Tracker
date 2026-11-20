"""Dashboard ("control room") figures: per-flock next action, entries done today,
feed on farms, pending orders, 14-day trends, regions and idle farms.

Works on PRIMED flocks (core.prime) — no per-flock queries.
"""
import datetime
from collections import defaultdict

from .standards import get_daily_feed_intake
from .serializers import person

TREND_DAYS = 14
FEED_DAYS_WARNING = 2       # fewer days of feed than this on the farm → "Order feed"


def _next_action(flock, age, live, entry_today, last_entry, stock_bags, today):
    if live <= 0 and flock.total_sold_birds > 0:
        return {'code': 'bill', 'label': 'Close & bill', 'severity': 'info'}
    if age >= 1 and not entry_today:
        days = (today - last_entry).days if last_entry else age
        if days >= 2:
            return {'code': 'entry', 'label': f'No entry for {days} days', 'severity': 'danger'}
        return {'code': 'entry', 'label': 'Daily entry due', 'severity': 'warn'}
    need_per_day = live * get_daily_feed_intake(max(age, 0)) / 1000 / 50          # bags a day
    if need_per_day > 0 and stock_bags < need_per_day * FEED_DAYS_WARNING:
        return {'code': 'feed', 'label': 'Order feed', 'severity': 'warn'}
    return {'code': 'ok', 'label': 'On track', 'severity': 'ok'}


def control_room(active_flocks, farms, today):
    from .models import FeedOrder
    flocks = list(active_flocks)
    rows, trend_mort, trend_feed = [], defaultdict(int), defaultdict(float)
    start = today - datetime.timedelta(days=TREND_DAYS - 1)
    regions = {}
    for f in flocks:
        stats = f._stats
        entries = stats['entries'] if stats is not None else list(f.daily_entries.all())
        last_entry = entries[0].date if entries else None
        entry_today = last_entry == today
        for e in entries:
            if e.date >= start:
                trend_mort[e.date] += e.mortality_count
                trend_feed[e.date] += e.total_feed_bags
        age = (today - f.placement_date).days
        live = f.live_birds
        stock = f.flock_feed_stock
        wvs = f.weight_vs_standard
        action = _next_action(f, age, live, entry_today, last_entry, float(stock['total']), today)
        rows.append({
            'flock_id': f.id, 'farm_id': f.farm_id, 'farm_name': f.farm.name, 'farm_code': f.farm.farm_code,
            'region': f.farm.region, 'owner_name': f.farm.owner_name, 'age_days': age,
            'chicks': f.chick_count, 'live_birds': live, 'mortality_pct': f.mortality_percentage,
            'weight_pct': round(wvs['actual_g'] / wvs['standard_g'] * 100) if wvs and wvs['standard_g'] else None,
            'feed_bags': round(float(stock['total']), 1),
            'last_entry': last_entry.isoformat() if last_entry else None, 'entry_today': entry_today,
            'last_entry_by': person(entries[0].entered_by) if entries else None,
            'next_action': action,
        })
        r = regions.setdefault(f.farm.region or '—', {'region': f.farm.region or '—', 'farms': set(), 'flocks': 0,
                                                      'live_birds': 0, 'placed': 0, 'mortality': 0,
                                                      'entries_due': 0})
        r['farms'].add(f.farm_id)
        r['flocks'] += 1
        r['live_birds'] += live
        r['placed'] += f.chick_count
        r['mortality'] += f.total_mortality
        r['entries_due'] += 0 if entry_today or age < 1 else 1

    order = {'danger': 0, 'warn': 1, 'info': 2, 'ok': 3}
    rows.sort(key=lambda r: (order[r['next_action']['severity']], r['farm_name']))
    farm_ids = [f.id for f in farms]
    pending = FeedOrder.objects.filter(farm_id__in=farm_ids, status__in=('pending', 'sent'))
    pending_bags = sum(int(b) for b in pending.values_list('quantity_bags', flat=True))
    active_farm_ids = {f.farm_id for f in flocks}
    days = [start + datetime.timedelta(days=n) for n in range(TREND_DAYS)]
    return {
        'flock_rows': rows,
        'entries_today': {'done': sum(1 for r in rows if r['entry_today']),
                          'due': sum(1 for r in rows if r['age_days'] >= 1)},
        'feed_on_farms_bags': round(sum(r['feed_bags'] for r in rows), 1),
        'pending_orders': {'count': pending.count(), 'bags': pending_bags},
        'trend': {'dates': [d.isoformat() for d in days],
                  'mortality': [trend_mort.get(d, 0) for d in days],
                  'feed_bags': [round(trend_feed.get(d, 0), 1) for d in days]},
        'regions': sorted(({**r, 'farms': len(r['farms']),
                            'mortality_pct': round(r['mortality'] / r['placed'] * 100, 2) if r['placed'] else 0}
                           for r in regions.values()), key=lambda r: r['region']),
        'idle_farms': [{'id': f.id, 'name': f.name, 'farm_code': f.farm_code, 'region': f.region}
                       for f in farms if f.id not in active_farm_ids],
    }
