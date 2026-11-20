"""Best day to lift: hold the birds longer, or sell now?

For each active flock old enough to lift, compare lifting today with lifting on
each of the next HORIZON_DAYS days, from the company's side:

  value(day) = birds left × weight × (market price − grower charge per kg)
               − feed eaten from today until that day

  weight   last recorded body weight, carried forward on the Cobb curve at the
           same % of standard (no weight recorded → the standard itself)
  birds    live birds now, minus the flock's own recent daily death rate
           (last 7 days; the standard rate if no recent entries)
  feed     standard intake for each day's age × birds, at the finisher (last feed type)
           feed rate, or the bill-config feed cost
  price    the admin's market rate for today (or the latest within 7 days), else
           the weight-weighted rate of our own sales in the last 7 days. "Trend"
           mode carries HALF the recent daily change forward, capped at
           ±MAX_TREND_PER_DAY ₹/kg per day; "flat" keeps today's price.
"""
import datetime
from collections import defaultdict

from django.db.models import F, Sum

from .standards import get_daily_feed_intake, get_standard_weight

MIN_LIFT_AGE = 28
MAX_AGE = 56                       # the standard curve ends here
HORIZON_DAYS = 10
RATE_FRESH_DAYS = 7
TREND_WINDOW_DAYS = 14
TREND_SHARE = 0.5
MAX_TREND_PER_DAY = 1.5


class NoPrice(Exception):
    pass


def current_price(today):
    """(price ₹/kg, source text, as-of date)."""
    from .models import MarketRate, Sale
    rate = MarketRate.objects.filter(date__lte=today, date__gte=today - datetime.timedelta(days=RATE_FRESH_DAYS)) \
        .order_by('-date').first()
    if rate:
        when = 'today' if rate.date == today else rate.date.strftime('%d %b')
        return float(rate.rate_per_kg), f'Market rate ({when})', rate.date
    since = today - datetime.timedelta(days=RATE_FRESH_DAYS)
    agg = Sale.objects.filter(date__gte=since, date__lte=today, rate_per_kg__isnull=False, total_weight_kg__gt=0) \
        .aggregate(value=Sum(F('total_weight_kg') * F('rate_per_kg')), kg=Sum('total_weight_kg'))
    if agg['kg']:
        return round(float(agg['value']) / float(agg['kg']), 2), 'Average of our sales in the last 7 days', today
    raise NoPrice('No market rate in the last 7 days and no recent sales — enter today\'s market rate.')


def price_trend(today):
    """Recent ₹/kg change per day from the admin's market rates (least squares), or 0."""
    from .models import MarketRate
    pts = list(MarketRate.objects.filter(date__lte=today, date__gte=today - datetime.timedelta(days=TREND_WINDOW_DAYS))
               .values_list('date', 'rate_per_kg'))
    if len(pts) < 3:
        return 0.0
    xs = [(d - today).days for d, _ in pts]
    ys = [float(r) for _, r in pts]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den if den else 0.0


def assumed_daily_change(trend_per_day):
    return max(-MAX_TREND_PER_DAY, min(MAX_TREND_PER_DAY, trend_per_day * TREND_SHARE))


def feed_cost_per_kg():
    from .models import BillConfig, FeedRate
    from .feedtypes import finisher_key
    r = FeedRate.objects.filter(feed_type=finisher_key()).order_by('-week_start_date').first()
    return float(r.rate_per_kg) if r else float(BillConfig.get_active().feed_cost_per_kg)


def plan_flock(flock, today, entries, sold, *, price, daily_change, feed_rate, grower_charge, default_mort_rate):
    """Day-by-day value of lifting today … +HORIZON_DAYS, and the best day.
    `entries`: the flock's daily entries (dicts, by date); `sold`: birds sold so far."""
    age = (today - flock.placement_date).days
    gone = sum(e['mortality_count'] + e['cull_count'] for e in entries)
    birds = flock.chick_count - gone - sold
    weighed = [e for e in entries if e['avg_body_weight_grams']]
    if weighed:
        w = weighed[-1]
        std_then = get_standard_weight((w['date'] - flock.placement_date).days)
        perf = float(w['avg_body_weight_grams']) / std_then if std_then else 1.0
        weight_source = f"weighed {w['date']:%d %b} ({perf * 100:.0f}% of standard)"
    else:
        perf, weight_source = 1.0, 'no weight recorded — using the standard'

    recent = [e for e in entries if e['date'] > today - datetime.timedelta(days=7)]
    if recent and birds > 0:
        lost = sum(e['mortality_count'] + e['cull_count'] for e in recent)
        mort_rate = lost / len(recent) / max(birds + lost, 1)
    else:
        mort_rate = default_mort_rate

    days, feed_so_far, alive = [], 0.0, float(max(birds, 0))
    for k in range(0, HORIZON_DAYS + 1):
        a = age + k
        if a > MAX_AGE:
            break
        if k > 0:
            # yesterday's feed, then yesterday's deaths
            feed_so_far += alive * get_daily_feed_intake(a - 1) / 1000.0 * feed_rate
            alive *= (1 - mort_rate)
        weight_kg = get_standard_weight(a) * perf / 1000.0
        p = price + daily_change * k
        value = alive * weight_kg * (p - grower_charge) - feed_so_far
        days.append({'date': (today + datetime.timedelta(days=k)).isoformat(), 'age': a,
                     'birds': round(alive), 'weight_kg': round(weight_kg, 3), 'price': round(p, 2),
                     'live_kg': round(alive * weight_kg), 'feed_cost': round(feed_so_far),
                     'value': round(value)})
    base = days[0]['value']
    for d in days:
        d['gain_vs_today'] = d['value'] - base
    best = max(days, key=lambda d: d['value'])
    k_best = days.index(best)
    if k_best == 0:
        advice = 'Lift now — holding longer costs more feed than the birds gain in value.'
    elif k_best == len(days) - 1 and best['age'] < MAX_AGE:
        advice = (f"Holding still pays at the end of the {HORIZON_DAYS}-day window — "
                  f"check again in a few days.")
    else:
        advice = f"Best around {best['date']} (day {best['age']}): about ₹{best['gain_vs_today']:,} more than lifting today."
    return {
        'flock_id': flock.id, 'farm_name': flock.farm.name, 'farm_code': flock.farm.farm_code,
        'region': flock.farm.region, 'age_today': age, 'live_birds': birds,
        'weight_today_kg': days[0]['weight_kg'], 'weight_source': weight_source,
        'performance_pct': round(perf * 100, 1), 'daily_mortality_pct': round(mort_rate * 100, 3),
        'best_date': best['date'], 'best_age': best['age'], 'best_in_days': k_best,
        'gain_vs_today': best['gain_vs_today'], 'advice': advice, 'days': days,
    }


def lift_plan(flocks, today, trend=True):
    from .models import BillConfig
    price, source, as_of = current_price(today)
    slope = price_trend(today)
    change = assumed_daily_change(slope) if trend else 0.0
    cfg = BillConfig.get_active()
    feed_rate = feed_cost_per_kg()
    grower = float(cfg.standard_growing_charges)
    default_mort = float(cfg.standard_mortality_pct) / 100.0 / 42.0
    from .models import DailyEntry, Sale
    flocks = [f for f in flocks if MIN_LIFT_AGE <= (today - f.placement_date).days <= MAX_AGE]
    ids = [f.id for f in flocks]
    entries = defaultdict(list)
    for e in DailyEntry.objects.filter(flock_id__in=ids).order_by('date').values(
            'flock_id', 'date', 'mortality_count', 'cull_count', 'avg_body_weight_grams'):
        entries[e['flock_id']].append(e)
    sold = dict(Sale.objects.filter(flock_id__in=ids).values('flock_id').annotate(n=Sum('bird_count'))
                .values_list('flock_id', 'n'))
    rows = [plan_flock(f, today, entries[f.id], sold.get(f.id) or 0, price=price, daily_change=change,
                       feed_rate=feed_rate, grower_charge=grower, default_mort_rate=default_mort)
            for f in flocks]
    rows = [r for r in rows if r['live_birds'] > 0]
    rows.sort(key=lambda r: (r['best_in_days'], -r['gain_vs_today'], r['farm_name']))
    return {
        'as_of': today.isoformat(),
        'price': {'per_kg': price, 'source': source, 'date': as_of.isoformat(),
                  'recent_trend_per_day': round(slope, 2), 'assumed_change_per_day': round(change, 2),
                  'mode': 'trend' if trend else 'flat'},
        'costs': {'feed_per_kg': feed_rate, 'grower_charge_per_kg': grower},
        'min_age': MIN_LIFT_AGE, 'horizon_days': HORIZON_DAYS,
        'flocks': rows,
        'summary': {'flocks': len(rows), 'lift_now': sum(1 for r in rows if r['best_in_days'] == 0),
                    'hold': sum(1 for r in rows if r['best_in_days'] > 0),
                    'total_gain': sum(r['gain_vs_today'] for r in rows)},
    }
