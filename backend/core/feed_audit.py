"""Feed leakage detector.

Feed is ~70% of a broiler's cost, and in contract farming the quiet loss is
feed that leaves the farm (sold, moved to another flock) while the paperwork
says it was eaten. Four signals, per flock:

  COUNT_SHORT   physical bag count is below paper stock          (high)
  COUNT_EXCESS  physical count is above paper stock — feeding
                recorded that did not happen                       (medium)
  OVER_STANDARD recorded feed well above the age standard while
                birds are not heavier than standard              (high / medium)
  LEFT_AT_CLOSE paper says feed was left when the flock closed and
                it was never moved                                 (high)
  COUNT_DUE     no bag count in the last COUNT_EVERY_DAYS days      (low)

Paper ("book") stock = delivered + transferred in − transferred out − recorded
as eaten, up to and including a date. All data for many flocks is loaded in a
fixed number of queries (no per-flock queries).
"""
import datetime
from collections import defaultdict
from decimal import Decimal

from django.utils import timezone

from .standards import get_daily_feed_intake, get_standard_weight

BAG_KG = 50
FEED_TYPES = ('BPSC', 'BSC', 'BFP')
SHORT_MIN_BAGS = 2          # a gap smaller than this is counting noise
SHORT_PCT = 2.0             # … or smaller than this % of feed received
OVER_STANDARD_PCT = 10.0    # recorded feed above standard by more than this
UNDERWEIGHT_PCT = 95.0      # weight below this % of standard counts as "not heavier"
COUNT_EVERY_DAYS = 7
MIN_AGE_FOR_CHECKS = 7
CLOSED_LOOKBACK_DAYS = 45

SEVERITY_ORDER = {'high': 0, 'medium': 1, 'low': 2}


def _day(value):
    """A DateField value, or a DateTimeField value as a local (IST) date."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return timezone.localdate(value) if timezone.is_aware(value) else value.date()
    return value


class FeedData:
    """Everything the audit needs for a set of flocks, in 6 queries."""

    def __init__(self, flocks):
        from .models import DailyEntry, FeedOrder, FeedStockCount, FeedTransfer, Sale
        ids = [f.id for f in flocks]
        self.entries = defaultdict(list)
        for e in DailyEntry.objects.filter(flock_id__in=ids).values(
                'flock_id', 'date', 'mortality_count', 'cull_count',
                'feed_bpsc_bags', 'feed_bsc_bags', 'feed_bfp_bags', 'avg_body_weight_grams'):
            self.entries[e['flock_id']].append(e)
        self.moves = defaultdict(list)            # (date or None, feed_type, +bags/-bags)
        for o in FeedOrder.objects.filter(flock_id__in=ids, status='delivered').values(
                'flock_id', 'feed_type', 'quantity_bags', 'delivered_date'):
            self.moves[o['flock_id']].append((_day(o['delivered_date']), o['feed_type'], o['quantity_bags']))
        for t in FeedTransfer.objects.filter(to_flock_id__in=ids).values(
                'to_flock_id', 'feed_type', 'quantity_bags', 'date'):
            self.moves[t['to_flock_id']].append((t['date'], t['feed_type'], t['quantity_bags']))
        for t in FeedTransfer.objects.filter(from_flock_id__in=ids).values(
                'from_flock_id', 'feed_type', 'quantity_bags', 'date'):
            self.moves[t['from_flock_id']].append((t['date'], t['feed_type'], -t['quantity_bags']))
        self.sales = defaultdict(list)
        for s in Sale.objects.filter(flock_id__in=ids).values('flock_id', 'date', 'bird_count'):
            self.sales[s['flock_id']].append(s)
        self.counts = defaultdict(list)          # newest first
        for c in FeedStockCount.objects.filter(flock_id__in=ids).order_by('-date').values(
                'id', 'flock_id', 'date', 'bpsc_bags', 'bsc_bags', 'bfp_bags'):
            self.counts[c['flock_id']].append(c)


def book_stock(data, flock_id, as_of=None):
    """Paper stock per feed type (bags) at the end of `as_of` (None = all time).
    Deliveries with no recorded delivery date count as already received."""
    stock = dict.fromkeys(FEED_TYPES, 0)
    received = 0
    for day, ft, bags in data.moves[flock_id]:
        if as_of is None or day is None or day <= as_of:
            stock[ft] = stock.get(ft, 0) + bags
            received += max(bags, 0)
    for e in data.entries[flock_id]:
        if as_of is None or e['date'] <= as_of:
            stock['BPSC'] -= e['feed_bpsc_bags']
            stock['BSC'] -= e['feed_bsc_bags']
            stock['BFP'] -= e['feed_bfp_bags']
    stock['total'] = sum(stock[ft] for ft in FEED_TYPES)
    stock['received'] = received
    return stock


def book_stock_for(flock, as_of=None):
    """Convenience for one flock (a few queries)."""
    return book_stock(FeedData([flock]), flock.id, as_of)


def standard_feed_kg(flock, entries, sales, upto):
    """Feed the live birds should have eaten from placement to `upto`, per the
    age standard, with birds removed as they died, were culled or sold."""
    gone_by_day = defaultdict(int)
    for e in entries:
        gone_by_day[e['date']] += e['mortality_count'] + e['cull_count']
    for s in sales:
        gone_by_day[s['date']] += s['bird_count']
    alive = flock.chick_count
    total_g = 0.0
    day = flock.placement_date
    while day <= upto:
        age = (day - flock.placement_date).days
        total_g += max(alive, 0) * get_daily_feed_intake(age)
        alive -= gone_by_day.get(day, 0)        # removals take effect from the next day
        day += datetime.timedelta(days=1)
    return total_g / 1000.0


def _flag(code, severity, message, bags=0, kg=0.0):
    return {'code': code, 'severity': severity, 'message': message,
            'bags': bags, 'kg': round(kg, 1)}


def audit_flock(flock, data, today, feed_cost_per_kg):
    entries = data.entries[flock.id]
    sales = data.sales[flock.id]
    counts = data.counts[flock.id]
    flags = []
    book_now = book_stock(data, flock.id)
    age = (today - flock.placement_date).days

    # 1. Latest physical count vs paper stock at that date.
    last_count = None
    if counts:
        c = counts[0]
        book = book_stock(data, flock.id, c['date'])
        counted = {'BPSC': c['bpsc_bags'], 'BSC': c['bsc_bags'], 'BFP': c['bfp_bags']}
        counted['total'] = sum(counted.values())
        gap = book['total'] - counted['total']              # + = bags missing
        threshold = max(SHORT_MIN_BAGS, book['received'] * SHORT_PCT / 100.0)
        last_count = {'id': c['id'], 'date': c['date'].isoformat(), 'counted': counted,
                      'book': {k: book[k] for k in (*FEED_TYPES, 'total')}, 'gap_bags': gap}
        when = c['date'].strftime('%d %b')
        if gap >= threshold:
            flags.append(_flag('COUNT_SHORT', 'high',
                               f"{gap} bags short at the count on {when}: paper says {book['total']}, "
                               f"farm has {counted['total']}.", bags=gap, kg=gap * BAG_KG))
        elif -gap >= threshold:
            flags.append(_flag('COUNT_EXCESS', 'medium',
                               f"{-gap} more bags at the farm than on paper at the count on {when} — "
                               f"feeding was recorded that did not happen.", bags=-gap))

    # 2. Recorded feed vs the age standard, when birds are not heavier for it.
    if entries:
        last_day = max(e['date'] for e in entries)
        last_age = (last_day - flock.placement_date).days
        recorded_kg = sum(e['feed_bpsc_bags'] + e['feed_bsc_bags'] + e['feed_bfp_bags'] for e in entries) * BAG_KG
        std_kg = standard_feed_kg(flock, entries, sales, last_day)
        weighed = [e for e in entries if e['avg_body_weight_grams']]
        weight_pct = None
        if weighed:
            w = max(weighed, key=lambda e: e['date'])
            std_w = get_standard_weight((w['date'] - flock.placement_date).days)
            weight_pct = round(float(w['avg_body_weight_grams']) / std_w * 100, 1) if std_w else None
        over_pct = (recorded_kg - std_kg) / std_kg * 100 if std_kg else 0
        if last_age >= MIN_AGE_FOR_CHECKS and over_pct > OVER_STANDARD_PCT and \
                (weight_pct is None or weight_pct < UNDERWEIGHT_PCT):
            excess = recorded_kg - std_kg
            if weight_pct is None:
                msg = (f"Recorded feed is {over_pct:.0f}% above the standard for this age "
                       f"({recorded_kg:,.0f} kg vs {std_kg:,.0f} kg) and no body weight is recorded to explain it.")
                severity = 'medium'
            else:
                msg = (f"Recorded feed is {over_pct:.0f}% above the standard for this age "
                       f"({recorded_kg:,.0f} kg vs {std_kg:,.0f} kg), but birds are only "
                       f"{weight_pct:.0f}% of standard weight.")
                severity = 'high'
            flags.append(_flag('OVER_STANDARD', severity, msg, bags=round(excess / BAG_KG), kg=excess))
        consumption = {'recorded_kg': round(recorded_kg, 1), 'standard_kg': round(std_kg, 1),
                       'over_pct': round(over_pct, 1), 'weight_pct_of_standard': weight_pct}
    else:
        consumption = None

    # 3. Feed left on paper when the flock closed.
    if flock.status == 'closed' and book_now['total'] > 0:
        flags.append(_flag('LEFT_AT_CLOSE', 'high',
                           f"{book_now['total']} bags were left on paper when the flock closed and were "
                           f"never moved to another flock.", bags=book_now['total'], kg=book_now['total'] * BAG_KG))

    # 4. Count overdue.
    if flock.status == 'active' and age >= MIN_AGE_FOR_CHECKS:
        last = counts[0]['date'] if counts else None
        if last is None or (today - last).days > COUNT_EVERY_DAYS:
            flags.append(_flag('COUNT_DUE', 'low',
                               'No bag count yet.' if last is None else
                               f"Last bag count was {(today - last).days} days ago."))

    flags.sort(key=lambda f: SEVERITY_ORDER[f['severity']])
    # Money at risk: missing bags, over-recorded feed and feed left at close (not double-counted:
    # the largest single estimate, since they often describe the same missing feed).
    risk_kg = max([f['kg'] for f in flags if f['code'] in ('COUNT_SHORT', 'OVER_STANDARD', 'LEFT_AT_CLOSE')] or [0])
    return {
        'flock_id': flock.id, 'farm_id': flock.farm_id, 'farm_name': flock.farm.name,
        'farm_code': flock.farm.farm_code, 'region': flock.farm.region, 'status': flock.status,
        'age_days': age, 'placement_date': flock.placement_date.isoformat(),
        'book_stock': {k: book_now[k] for k in (*FEED_TYPES, 'total')},
        'received_bags': book_now['received'],
        'last_count': last_count, 'consumption': consumption,
        'flags': flags,
        'severity': flags[0]['severity'] if flags else None,
        'value_at_risk': round(risk_kg * float(feed_cost_per_kg)),
    }


def run_audit(flocks, today=None):
    from .models import BillConfig
    today = today or timezone.localdate()
    flocks = list(flocks)
    data = FeedData(flocks)
    cost = Decimal(BillConfig.get_active().feed_cost_per_kg)
    rows = [audit_flock(f, data, today, cost) for f in flocks]
    rows.sort(key=lambda r: (SEVERITY_ORDER.get(r['severity'], 9), -r['value_at_risk'], r['farm_name']))
    flagged = [r for r in rows if r['severity'] in ('high', 'medium')]
    return {
        'as_of': today.isoformat(),
        'feed_cost_per_kg': str(cost),
        'summary': {
            'flocks_checked': len(rows),
            'flagged': len(flagged),
            'high': sum(1 for r in rows if r['severity'] == 'high'),
            'counts_due': sum(1 for r in rows if any(f['code'] == 'COUNT_DUE' for f in r['flags'])),
            'value_at_risk': sum(r['value_at_risk'] for r in flagged),
        },
        'rows': rows,
    }
