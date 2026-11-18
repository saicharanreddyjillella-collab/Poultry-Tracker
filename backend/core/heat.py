"""Heat-stress forecast for broiler farms.

Weather: Open-Meteo hourly forecast (free, no API key) for one point per region,
cached for WEATHER_CACHE_SECONDS. Risk: the livestock Temperature-Humidity Index
THI = 0.8·T + RH/100·(T − 14.4) + 46.4   (T in °C, RH in %)
banded into levels, then adjusted for the birds and the shed:

  THI < 74 none · 74–78 watch · 79–83 danger · ≥ 84 emergency
  birds 28+ days (heavy)  → one level up (only if there is already some risk)
  chicks under 14 days    → two levels down (they need warmth; only extreme heat matters)
  EC (controlled) shed    → one level down

For tests and the browser test suite, WEATHER_FAKE=1 returns a fixed hot week
instead of calling the internet.
"""
import datetime
import json
import os
import urllib.parse
import urllib.request
from collections import defaultdict

from django.core.cache import cache

LEVELS = ('none', 'watch', 'danger', 'emergency')
FORECAST_DAYS = 5
WEATHER_CACHE_SECONDS = 2 * 60 * 60
OPEN_METEO_URL = 'https://api.open-meteo.com/v1/forecast'

ADVICE = {
    'watch': 'Plenty of cool, clean water; fans/foggers on from late morning; check drinkers twice in the afternoon.',
    'danger': 'All of the above, plus electrolytes / vitamin C in water, no feeding in the hottest hours '
              '(about 11 AM–4 PM), wet the roof or curtains, and avoid handling or moving birds.',
    'emergency': 'All of the above, plus lower stocking density where possible, keep a generator ready, '
                 'supervisor on the farm in the afternoon, and consider lifting heavy birds early.',
}


class WeatherUnavailable(Exception):
    pass


def thi(temp_c, rh_pct):
    return 0.8 * temp_c + (rh_pct / 100.0) * (temp_c - 14.4) + 46.4


def base_level(index):
    if index >= 84:
        return 'emergency'
    if index >= 79:
        return 'danger'
    if index >= 74:
        return 'watch'
    return 'none'


def farm_level(base, age_days, shed_type):
    i = LEVELS.index(base)
    if age_days < 14:
        i -= 2
    elif age_days >= 28 and i > 0:
        i += 1
    if shed_type == 'EC':
        i -= 1
    return LEVELS[max(0, min(i, len(LEVELS) - 1))]


def _fake_forecast(start):
    """A fixed hot spell: peaks (°C, RH%) per day, hottest at 14:00."""
    peaks = [(30, 50), (34, 45), (40, 40), (31, 55), (27, 60)]
    days = []
    for n, (tmax, rh_min) in enumerate(peaks):
        hours = []
        for h in range(24):
            drop = abs(h - 14) * 0.6
            hours.append((h, tmax - drop, min(95, rh_min + drop * 2)))
        days.append({'date': start + datetime.timedelta(days=n), 'hours': hours})
    return days


def fetch_forecast(lat, lon, start):
    """[{date, hours: [(hour, temp_c, rh_pct), …]}, …] for FORECAST_DAYS days from today (local)."""
    if os.environ.get('WEATHER_FAKE') == '1':
        return _fake_forecast(start)
    key = f'heat:forecast:{round(float(lat), 2)}:{round(float(lon), 2)}:{start.isoformat()}'
    cached = cache.get(key)
    if cached is not None:
        return cached
    query = urllib.parse.urlencode({
        'latitude': f'{float(lat):.4f}', 'longitude': f'{float(lon):.4f}',
        'hourly': 'temperature_2m,relative_humidity_2m',
        'timezone': 'Asia/Kolkata', 'forecast_days': FORECAST_DAYS,
    })
    try:
        with urllib.request.urlopen(f'{OPEN_METEO_URL}?{query}', timeout=8) as resp:
            payload = json.load(resp)
        hourly = payload['hourly']
        by_day = defaultdict(list)
        for stamp, t, rh in zip(hourly['time'], hourly['temperature_2m'], hourly['relative_humidity_2m']):
            if t is None or rh is None:
                continue
            moment = datetime.datetime.fromisoformat(stamp)
            by_day[moment.date()].append((moment.hour, float(t), float(rh)))
    except Exception as exc:  # network, timeout, unexpected payload
        raise WeatherUnavailable(str(exc)) from exc
    days = [{'date': d, 'hours': by_day[d]} for d in sorted(by_day) if d >= start][:FORECAST_DAYS]
    if not days:
        raise WeatherUnavailable('empty forecast')
    cache.set(key, days, WEATHER_CACHE_SECONDS)
    return days


def daily_risk(day):
    """Peak heat of one forecast day."""
    best = max(day['hours'], key=lambda h: thi(h[1], h[2]))
    index = thi(best[1], best[2])
    return {
        'date': day['date'].isoformat(),
        'peak_thi': round(index, 1),
        'peak_temp': round(best[1], 1),
        'peak_rh': round(best[2]),
        'peak_hour': best[0],
        'level': base_level(index),
    }


def heat_report(flocks, today):
    """Heat risk for each active flock's farm over the next FORECAST_DAYS days."""
    from .models import RegionLocation
    flocks = [f for f in flocks]
    regions = sorted({f.farm.region for f in flocks if f.farm.region})
    locations = {r.region: r for r in RegionLocation.objects.filter(region__in=regions)}
    region_rows, region_days = [], {}
    for name in regions:
        loc = locations.get(name)
        row = {'region': name, 'has_location': loc is not None, 'error': None, 'days': []}
        if loc:
            row.update(latitude=float(loc.latitude), longitude=float(loc.longitude))
            try:
                row['days'] = [daily_risk(d) for d in fetch_forecast(loc.latitude, loc.longitude, today)]
                region_days[name] = row['days']
            except WeatherUnavailable:
                row['error'] = 'Weather forecast is not available right now. Try again later.'
        region_rows.append(row)

    farm_rows = []
    for f in flocks:
        days = region_days.get(f.farm.region)
        if not days:
            continue
        cells = []
        for d in days:
            day = datetime.date.fromisoformat(d['date'])
            age = (day - f.placement_date).days
            cells.append({'date': d['date'], 'age': age,
                          'level': farm_level(d['level'], age, f.farm.shed_type)})
        worst = max(cells, key=lambda c: LEVELS.index(c['level']))
        farm_rows.append({
            'flock_id': f.id, 'farm_id': f.farm_id, 'farm_name': f.farm.name, 'farm_code': f.farm.farm_code,
            'region': f.farm.region, 'shed_type': f.farm.shed_type, 'age_today': (today - f.placement_date).days,
            'days': cells, 'worst_level': worst['level'], 'worst_date': worst['date'],
        })
    farm_rows.sort(key=lambda r: (-LEVELS.index(r['worst_level']), r['worst_date'], r['farm_name']))

    soon = {(today + datetime.timedelta(days=n)).isoformat() for n in range(3)}
    at_risk = [r for r in farm_rows
               if any(c['date'] in soon and c['level'] in ('danger', 'emergency') for c in r['days'])]
    return {
        'as_of': today.isoformat(),
        'dates': [(today + datetime.timedelta(days=n)).isoformat() for n in range(FORECAST_DAYS)],
        'regions': region_rows,
        'farms': farm_rows,
        'summary': {
            'at_risk_next_3_days': len(at_risk),
            'emergency_next_3_days': sum(1 for r in at_risk if any(
                c['date'] in soon and c['level'] == 'emergency' for c in r['days'])),
            'regions_missing_location': [r['region'] for r in region_rows if not r['has_location']],
        },
        'advice': ADVICE,
    }
