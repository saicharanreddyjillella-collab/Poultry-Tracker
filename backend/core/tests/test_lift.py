"""Best day to lift: price source and trend, the hold-or-sell maths, the market rate API."""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core import lift
from core.models import BillConfig, DailyEntry, Farm, FeedRate, Flock, MarketRate, Sale, UserProfile

pytestmark = pytest.mark.django_db
T = datetime.date.today()
D = datetime.timedelta


def client_for(username, role, regions=()):
    u = User.objects.create_user(username=username, password="pass12345")
    UserProfile.objects.create(user=u, role=role, assigned_regions=list(regions))
    c = APIClient()
    r = c.post("/api/auth/login/", {"username": username, "password": "pass12345"}, format="json")
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


_n = [0]


def flock(age, chicks=10000, weight=None, weighed_age=None, recent_deaths=0):
    _n[0] += 1
    farm = Farm.objects.create(farm_code=f"L{_n[0]}", name=f"Farm {_n[0]}", owner_name="o", region="Zone-A",
                               capacity=20000)
    f = Flock.objects.create(farm=farm, placement_date=T - D(days=age), chick_count=chicks)
    if weight:
        DailyEntry.objects.create(flock=f, date=f.placement_date + D(days=weighed_age or age),
                                  avg_body_weight_grams=Decimal(weight))
    for k in range(recent_deaths and 7):
        DailyEntry.objects.get_or_create(flock=f, date=T - D(days=k), defaults={"mortality_count": recent_deaths})
    return f


def plan(trend=True):
    return lift.lift_plan(Flock.objects.select_related("farm").filter(status="active"), T, trend=trend)


def row(f, trend=True):
    return next(r for r in plan(trend)["flocks"] if r["flock_id"] == f.id)


@pytest.fixture
def cfg(db):
    c = BillConfig.get_active()                    # feed ₹44/kg, grower ₹6.50/kg
    return c


# ── price ────────────────────────────────────────────────────────────────────

def test_todays_market_rate_wins(cfg):
    MarketRate.objects.create(date=T - D(days=2), rate_per_kg=95)
    MarketRate.objects.create(date=T, rate_per_kg=104)
    assert lift.current_price(T)[:2] == (104.0, "Market rate (today)")


def test_recent_rate_then_own_sales_then_a_clear_message(cfg):
    MarketRate.objects.create(date=T - D(days=10), rate_per_kg=90)        # too old
    f = flock(40)
    Sale.objects.create(flock=f, date=T - D(days=1), bird_count=10, total_weight_kg=100, rate_per_kg=100)
    Sale.objects.create(flock=f, date=T - D(days=2), bird_count=10, total_weight_kg=300, rate_per_kg=108)
    assert lift.current_price(T)[:2] == (106.0, "Average of our sales in the last 7 days")
    Sale.objects.all().delete()
    with pytest.raises(lift.NoPrice):
        lift.current_price(T)
    MarketRate.objects.create(date=T - D(days=3), rate_per_kg=99)
    price, source, _ = lift.current_price(T)
    assert price == 99.0 and "Market rate" in source


def test_trend_uses_half_the_recent_change_and_is_capped(cfg):
    for k, rate in enumerate([100, 101, 102, 103, 104]):                  # +₹1/day
        MarketRate.objects.create(date=T - D(days=4 - k), rate_per_kg=rate)
    assert lift.price_trend(T) == pytest.approx(1.0)
    assert lift.assumed_daily_change(1.0) == 0.5
    assert lift.assumed_daily_change(8.0) == lift.MAX_TREND_PER_DAY
    assert lift.assumed_daily_change(-8.0) == -lift.MAX_TREND_PER_DAY


def test_too_few_rates_means_no_trend(cfg):
    MarketRate.objects.create(date=T, rate_per_kg=100)
    MarketRate.objects.create(date=T - D(days=1), rate_per_kg=90)
    assert lift.price_trend(T) == 0.0


# ── hold or sell ─────────────────────────────────────────────────────────────

def test_low_price_means_lift_now(cfg):
    MarketRate.objects.create(date=T, rate_per_kg=60)
    f = flock(38)
    r = row(f)
    assert r["best_in_days"] == 0 and r["advice"].startswith("Lift now")
    assert all(d["gain_vs_today"] <= 0 for d in r["days"])


def test_good_price_means_hold_and_shows_the_gain(cfg):
    MarketRate.objects.create(date=T, rate_per_kg=130)
    f = flock(30)
    r = row(f)
    assert r["best_in_days"] > 0 and r["gain_vs_today"] > 0
    best = r["days"][r["best_in_days"]]
    assert best["value"] - r["days"][0]["value"] == r["gain_vs_today"]
    assert "more than lifting today" in r["advice"] or "check again" in r["advice"]


def test_value_is_birds_times_weight_times_margin_minus_feed(cfg):
    MarketRate.objects.create(date=T, rate_per_kg=110)
    f = flock(35, chicks=1000)
    d0, d1 = row(f, trend=False)["days"][:2]
    margin = 110 - 6.5
    assert d0["value"] == round(1000 * d0["weight_kg"] * margin)
    feed = 1000 * lift.get_daily_feed_intake(35) / 1000 * 44
    mort = cfg.standard_mortality_pct / 100 / 42
    birds = 1000 * (1 - float(mort))
    assert d1["feed_cost"] == round(feed)
    assert d1["value"] == round(birds * d1["weight_kg"] * margin - feed)


def test_finisher_feed_rate_is_used_when_entered(cfg):
    FeedRate.objects.create(week_start_date=T, feed_type="BFP", rate_per_kg=50)
    MarketRate.objects.create(date=T, rate_per_kg=110)
    flock(35)
    assert plan()["costs"]["feed_per_kg"] == 50.0


def test_underweight_flock_is_projected_below_standard(cfg):
    MarketRate.objects.create(date=T, rate_per_kg=110)
    f = flock(35, weight=1796, weighed_age=35)                    # 90% of 1996 g
    r = row(f)
    assert r["performance_pct"] == 90.0 and "90% of standard" in r["weight_source"]
    assert r["days"][0]["weight_kg"] == pytest.approx(1.796, abs=0.002)
    assert r["days"][1]["weight_kg"] == pytest.approx(lift.get_standard_weight(36) * 0.9 / 1000, abs=0.002)


def test_heavy_recent_deaths_push_the_lift_earlier(cfg):
    MarketRate.objects.create(date=T, rate_per_kg=118)
    calm, sick = flock(33), flock(33, recent_deaths=200)          # 2% a day
    assert row(sick)["best_in_days"] < row(calm)["best_in_days"]
    assert row(sick)["daily_mortality_pct"] > 1.5


def test_young_and_too_old_flocks_are_left_out(cfg):
    MarketRate.objects.create(date=T, rate_per_kg=110)
    young, ready, old = flock(20), flock(30), flock(60)
    ids = [r["flock_id"] for r in plan()["flocks"]]
    assert ready.id in ids and young.id not in ids and old.id not in ids


def test_horizon_stops_at_the_end_of_the_growth_curve(cfg):
    MarketRate.objects.create(date=T, rate_per_kg=110)
    f = flock(52)
    assert [d["age"] for d in row(f)["days"]] == [52, 53, 54, 55, 56]


# ── API ──────────────────────────────────────────────────────────────────────

def test_planner_is_admin_only_and_explains_a_missing_price(cfg):
    admin, sup = client_for("boss", "admin"), client_for("sup", "supervisor", ["Zone-A"])
    assert sup.get("/api/reports/lift-planner/").status_code == 403
    flock(35)
    r = admin.get("/api/reports/lift-planner/")
    assert r.status_code == 200 and r.data["needs_rate"] and "enter today's market rate" in r.data["error"]
    MarketRate.objects.create(date=T, rate_per_kg=110)
    r = admin.get("/api/reports/lift-planner/?trend=0").data
    assert r["price"]["mode"] == "flat" and r["summary"]["flocks"] == 1


def test_market_rate_entry_corrects_the_same_day(cfg):
    admin, sup = client_for("boss", "admin"), client_for("sup", "supervisor")
    assert sup.post("/api/market-rates/", {"date": str(T), "rate_per_kg": "100"}, format="json").status_code == 403
    assert admin.post("/api/market-rates/", {"date": str(T), "rate_per_kg": "100"}, format="json").status_code == 201
    r = admin.post("/api/market-rates/", {"date": str(T), "rate_per_kg": "102.50"}, format="json")
    assert r.status_code == 200 and r.data["rate_per_kg"] == "102.50"
    assert MarketRate.objects.count() == 1


@pytest.mark.parametrize("body,field", [({"date": str(T + D(days=1)), "rate_per_kg": "100"}, "date"),
                                        ({"date": str(T), "rate_per_kg": "4"}, "rate_per_kg"),
                                        ({"date": str(T), "rate_per_kg": "1050"}, "rate_per_kg")])
def test_bad_market_rates_are_explained(cfg, body, field):
    r = client_for("boss", "admin").post("/api/market-rates/", body, format="json")
    assert r.status_code == 400 and field in r.data
