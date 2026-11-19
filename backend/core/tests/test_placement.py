"""Who gets the next chicks: grower scores from settled flocks, availability, the placement plan."""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Bill, Farm, FeatureSetting, Flock, UserProfile
from core.placement import _percentiles, placement_report

pytestmark = pytest.mark.django_db
T = datetime.date.today()
D = datetime.timedelta


def client_for(username, role):
    u = User.objects.create_user(username=username, password="pass12345")
    UserProfile.objects.create(user=u, role=role, assigned_regions=["Zone-A"])
    c = APIClient()
    r = c.post("/api/auth/login/", {"username": username, "password": "pass12345"}, format="json")
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


def farm(code, capacity=5000, region="Zone-A"):
    return Farm.objects.create(farm_code=code, name=f"Farm {code}", owner_name=f"Owner {code}", region=region,
                               capacity=capacity)


def cycle(f, fcr, mort_pct, settled_days_ago=30, chicks=5000):
    """A closed, billed flock with this FCR and mortality %."""
    fl = Flock.objects.create(farm=f, placement_date=T - D(days=settled_days_ago + 42), chick_count=chicks,
                              status="closed")
    sold_kg = Decimal("10000")
    dead = round(chicks * mort_pct / 100)
    values = dict(flock=fl, chicks_placed=chicks, total_mortality=dead, live_birds=0,
                  total_sold_birds=chicks - dead, total_sold_weight_kg=sold_kg, avg_selling_price=Decimal("100"),
                  age_days=42, total_feed_kg=sold_kg * Decimal(str(fcr)))
    for field in Bill._meta.concrete_fields:          # every other required number → 0
        if field.name not in values and not field.null and not field.has_default() and not field.primary_key \
                and field.get_internal_type() in ("DecimalField", "PositiveIntegerField", "IntegerField",
                                                  "FloatField"):
            values[field.name] = 0
    b = Bill.objects.create(**values)
    Bill.objects.filter(pk=b.pk).update(generated_at=timezone.now() - D(days=settled_days_ago))
    return fl


def report(**kw):
    return placement_report(Farm.objects.all(), T, **kw)


def by_code(data):
    return {r["farm_code"]: r for r in data["growers"] + data["new_growers"]}


# ── score ────────────────────────────────────────────────────────────────────

def test_percentiles_best_is_100_and_ties_share():
    assert _percentiles({"a": 1.5, "b": 1.6, "c": 1.7}) == {"a": 100.0, "b": 50.0, "c": 0.0}
    assert _percentiles({"a": 1.5, "b": 1.5}) == {"a": 50.0, "b": 50.0}
    assert _percentiles({"a": 1.5}) == {"a": 100.0}


def test_better_fcr_and_lower_mortality_rank_first(db):
    good, mid, poor = farm("G"), farm("M"), farm("P")
    for f, fcr, mort in ((good, 1.55, 3), (mid, 1.65, 4), (poor, 1.80, 7)):
        cycle(f, fcr, mort, 100)
        cycle(f, fcr + 0.02, mort, 30)
    data = report()
    assert [r["farm_code"] for r in data["growers"]] == ["G", "M", "P"]
    g = by_code(data)["G"]
    assert g["rank"] == 1 and g["cycle_count"] == 2
    assert g["parts"] == {"fcr": 100.0, "mortality": 100.0, "consistency": 50.0}      # equal spreads → middle
    assert g["score"] == 90.0
    assert g["avg_fcr"] == pytest.approx(1.56) and g["avg_mortality_pct"] == 3.0
    assert by_code(data)["P"]["score"] == 10.0


def test_consistency_breaks_ties(db):
    steady, swingy = farm("S"), farm("W")
    cycle(steady, 1.60, 4, 100); cycle(steady, 1.60, 4, 30)
    cycle(swingy, 1.50, 4, 100); cycle(swingy, 1.70, 4, 30)               # same average FCR, more spread
    d = by_code(report())
    assert d["S"]["parts"]["consistency"] == 100.0 and d["W"]["parts"]["consistency"] == 0.0
    assert d["S"]["score"] > d["W"]["score"]


def test_only_last_four_cycles_in_two_years_count(db):
    f = farm("F")
    cycle(f, 3.0, 20, 800)                                                # too old
    for days in (300, 200, 120, 60, 25):
        cycle(f, 1.6 if days != 300 else 2.5, 4, days)                    # the 300-day one is the 5th newest
    r = by_code(report())["F"]
    assert r["cycle_count"] == 4 and r["avg_fcr"] == pytest.approx(1.6)


def test_new_grower_is_not_scored(db):
    farm("N")
    cycle(farm("X"), 1.6, 4)
    data = report()
    assert [r["farm_code"] for r in data["new_growers"]] == ["N"]
    assert by_code(data)["N"]["score"] is None and data["summary"] == {"scored": 1, "new": 1, "free_now": 2}


# ── availability ─────────────────────────────────────────────────────────────

def test_busy_resting_unbilled_and_free(db):
    busy, rest, unbilled, free = farm("B"), farm("R"), farm("U"), farm("F")
    Flock.objects.create(farm=busy, placement_date=T - D(days=20), chick_count=5000)
    cycle(rest, 1.6, 4, settled_days_ago=5)
    Flock.objects.create(farm=unbilled, placement_date=T - D(days=50), chick_count=5000, status="closed")
    cycle(free, 1.6, 4, settled_days_ago=20)
    d = by_code(report())
    assert d["B"]["availability"] == "Flock running (20 days old)" and not d["B"]["available"]
    assert d["R"]["availability"] == "Resting: settled 5 days ago, needs 14"
    assert d["U"]["availability"] == "Last flock closed but not billed yet"
    assert d["F"]["available"] and d["F"]["availability"] == "Free"
    assert by_code(report(rest_days=3))["R"]["available"]


# ── plan ─────────────────────────────────────────────────────────────────────

def test_plan_fills_best_free_farms_first_then_new_growers(db):
    a, b, c = farm("A", 6000), farm("B", 5000), farm("C", 4000)
    cycle(a, 1.55, 3); cycle(b, 1.70, 5); cycle(c, 1.62, 4)
    farm("NEW", 3000)
    plan = report(chicks=14000)["plan"]
    rows = [(p["farm_code"], p["chicks"]) for p in plan["rows"]]
    assert rows[:2] == [("A", 6000), ("C", 4000)]
    # 4,000 left: B needs ≥ 4,750 (±5%) → skipped; NEW (3,000) takes 3,000
    assert rows[2:] == [("NEW", 3000)] and plan["left_over"] == 1000 and plan["allocated"] == 13000


def test_partial_fill_within_five_percent_is_allowed(db):
    a = farm("A", 5000)
    cycle(a, 1.6, 4)
    plan = report(chicks=4800)["plan"]
    assert plan["rows"][0]["chicks"] == 4800 and plan["left_over"] == 0


def test_busy_farms_get_nothing(db):
    a, b = farm("A", 5000), farm("B", 5000)
    cycle(a, 1.5, 3); cycle(b, 1.7, 5)
    Flock.objects.create(farm=a, placement_date=T - D(days=3), chick_count=5000)
    assert [p["farm_code"] for p in report(chicks=10000)["plan"]["rows"]] == ["B"]


# ── API ──────────────────────────────────────────────────────────────────────

def test_admin_only_with_inputs_checked_and_switchable(db):
    admin, sup = client_for("boss", "admin"), client_for("sup", "supervisor")
    a = farm("A"); cycle(a, 1.6, 4)
    farm("Z", region="Zone-B")
    assert sup.get("/api/reports/grower-ranking/").status_code == 403
    r = admin.get("/api/reports/grower-ranking/?chicks=5000&region=Zone-A")
    assert r.status_code == 200 and r.data["plan"]["allocated"] == 5000
    assert [x["farm_code"] for x in r.data["growers"] + r.data["new_growers"]] == ["A"]
    assert r.data["regions"] == ["Zone-A", "Zone-B"]
    assert admin.get("/api/reports/grower-ranking/?chicks=lots").status_code == 400
    assert admin.get("/api/reports/grower-ranking/?rest_days=500").status_code == 400
    FeatureSetting.objects.create(key="placement_planner", enabled=False)
    r = admin.get("/api/reports/grower-ranking/")
    assert r.status_code == 403 and "turned off" in str(r.data["detail"])
