"""Who gets the next chicks: rank growers on past results and plan a placement.

Score (0–100) per farm from its last MAX_CYCLES settled (billed) flocks in the
last LOOKBACK_DAYS, using the bill's final numbers:
  FCR (feed kg ÷ live kg sold; lower is better)       45%
  mortality % (lower is better)                        35%
  consistency: spread of FCR between cycles            20%  (one cycle → middle value)
Each part is a percentile among the scored growers (best = 100), so a score
says "better than X% of your growers". Farms with no settled cycle are "new".

Placement: farms with no active flock whose last flock was settled at least
`rest_days` ago (cleaning) can take chicks. Chicks go to the best-scored free
farms first, then new growers; each farm gets its capacity — or the chicks left
when that is still within the ±5% capacity rule — and is skipped otherwise.
"""
from django.utils import timezone
import datetime
import statistics

WEIGHTS = {'fcr': 0.45, 'mortality': 0.35, 'consistency': 0.20}
MAX_CYCLES = 4
LOOKBACK_DAYS = 730
CAPACITY_TOLERANCE = 0.05


def _percentiles(values, lower_is_better=True):
    """{key: 0–100} — share of others this one beats (ties share), best = 100."""
    keys = [k for k, v in values.items() if v is not None]
    if len(keys) == 1:
        return {keys[0]: 100.0}
    out = {}
    for k in keys:
        v = values[k]
        better = sum(1 for o in keys if o != k and (values[o] > v if lower_is_better else values[o] < v))
        ties = sum(1 for o in keys if o != k and values[o] == v)
        out[k] = round((better + ties / 2) / (len(keys) - 1) * 100, 1)
    return out


def grower_scores(farms, today):
    """Rows for every farm: past cycles, averages, score parts, score (None for new growers)."""
    from .models import Bill
    since = today - datetime.timedelta(days=LOOKBACK_DAYS)
    farm_ids = [f.id for f in farms]
    cycles = {}
    for b in (Bill.objects.filter(flock__farm_id__in=farm_ids, flock__deleted_at__isnull=True,
                                  generated_at__date__gte=since)
              .select_related('flock').order_by('-generated_at')):
        sold = float(b.total_sold_weight_kg or 0)
        if not sold or not b.chicks_placed:
            continue
        rows = cycles.setdefault(b.flock.farm_id, [])
        if len(rows) < MAX_CYCLES:
            rows.append({'flock_id': b.flock_id, 'closed': timezone.localdate(b.generated_at).isoformat(),
                         'placement_date': b.flock.placement_date.isoformat(),
                         'fcr': round(float(b.total_feed_kg) / sold, 3),
                         'mortality_pct': round(b.total_mortality / b.chicks_placed * 100, 2),
                         'avg_weight_kg': round(sold / b.total_sold_birds, 3) if b.total_sold_birds else None,
                         'age_days': b.age_days})

    rows = {}
    for f in farms:
        cs = cycles.get(f.id, [])
        fcrs = [c['fcr'] for c in cs]
        rows[f.id] = {
            'farm_id': f.id, 'farm_code': f.farm_code, 'farm_name': f.name, 'owner_name': f.owner_name,
            'region': f.region, 'capacity': f.capacity, 'shed_type': f.shed_type,
            'cycles': cs, 'cycle_count': len(cs),
            'avg_fcr': round(statistics.mean(fcrs), 3) if cs else None,
            'avg_mortality_pct': round(statistics.mean(c['mortality_pct'] for c in cs), 2) if cs else None,
            'fcr_spread': round(statistics.pstdev(fcrs), 3) if len(cs) >= 2 else None,
            'last_closed': cs[0]['closed'] if cs else None,
        }
    scored = {k: r for k, r in rows.items() if r['cycle_count']}
    p_fcr = _percentiles({k: r['avg_fcr'] for k, r in scored.items()})
    p_mort = _percentiles({k: r['avg_mortality_pct'] for k, r in scored.items()})
    p_cons = _percentiles({k: r['fcr_spread'] for k, r in scored.items()})
    for k, r in rows.items():
        if k not in scored:
            r['parts'], r['score'] = None, None
            continue
        parts = {'fcr': p_fcr[k], 'mortality': p_mort[k], 'consistency': p_cons.get(k, 50.0)}
        r['parts'] = parts
        r['score'] = round(sum(parts[p] * w for p, w in WEIGHTS.items()), 1)
    return rows


def availability(farms, today, rest_days):
    """{farm_id: (free?, reason)} — busy with a flock, resting after one, or free."""
    from .models import Bill, Flock
    active = {f.farm_id: f for f in Flock.objects.filter(farm__in=farms, status='active')}
    last_bill = {}
    for b in (Bill.objects.filter(flock__farm__in=farms, flock__deleted_at__isnull=True)
              .select_related('flock').order_by('generated_at')):
        last_bill[b.flock.farm_id] = timezone.localdate(b.generated_at)
    closed_unbilled = set(Flock.objects.filter(farm__in=farms, status='closed', bill__isnull=True)
                          .values_list('farm_id', flat=True))
    out = {}
    for f in farms:
        if f.id in active:
            fl = active[f.id]
            out[f.id] = (False, f'Flock running ({(today - fl.placement_date).days} days old)')
        elif f.id in closed_unbilled:
            out[f.id] = (False, 'Last flock closed but not billed yet')
        elif f.id in last_bill and (today - last_bill[f.id]).days < rest_days:
            days = (today - last_bill[f.id]).days
            out[f.id] = (False, f'Resting: settled {days} day{"s" if days != 1 else ""} ago, needs {rest_days}')
        else:
            out[f.id] = (True, 'Free')
    return out


def plan_placement(rows, free, chicks):
    """Fill free farms in order (scored best-first, then new growers)."""
    order = sorted([r for r in rows.values() if free[r['farm_id']][0] and r['score'] is not None],
                   key=lambda r: (-r['score'], r['farm_name']))
    order += sorted([r for r in rows.values() if free[r['farm_id']][0] and r['score'] is None],
                    key=lambda r: r['farm_name'])
    left, plan = chicks, []
    for r in order:
        cap = r['capacity'] or 0
        if cap <= 0 or left <= 0:
            continue
        give = min(cap, left)
        if give < cap * (1 - CAPACITY_TOLERANCE):
            continue                      # too few chicks left to fill this farm within ±5%
        plan.append({'farm_id': r['farm_id'], 'farm_name': r['farm_name'], 'farm_code': r['farm_code'],
                     'region': r['region'], 'score': r['score'], 'capacity': cap, 'chicks': give})
        left -= give
    return {'rows': plan, 'allocated': chicks - left, 'left_over': left}


def placement_report(farms, today, chicks=0, rest_days=14):
    farms = list(farms)
    rows = grower_scores(farms, today)
    free = availability(farms, today, rest_days)
    for k, r in rows.items():
        r['available'], r['availability'] = free[k]
    ranked = sorted([r for r in rows.values() if r['score'] is not None], key=lambda r: (-r['score'], r['farm_name']))
    for i, r in enumerate(ranked, 1):
        r['rank'] = i
    new = sorted([r for r in rows.values() if r['score'] is None], key=lambda r: r['farm_name'])
    return {
        'as_of': today.isoformat(), 'weights': WEIGHTS, 'max_cycles': MAX_CYCLES, 'rest_days': rest_days,
        'growers': ranked, 'new_growers': new,
        'plan': plan_placement(rows, free, chicks) if chicks > 0 else None,
        'summary': {'scored': len(ranked), 'new': len(new),
                    'free_now': sum(1 for r in rows.values() if r['available'])},
    }
