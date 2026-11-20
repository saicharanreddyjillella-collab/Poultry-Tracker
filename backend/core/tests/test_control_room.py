"""Dashboard control-room figures: next action per flock, entries today, feed, trends, regions."""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import DailyEntry, Farm, FeedOrder, Flock, Sale, UserProfile

pytestmark = pytest.mark.django_db
T = datetime.date.today()
D = datetime.timedelta


def client_for(username, role, regions=()):
    u = User.objects.create_user(username=username, password="pass12345")
    p = UserProfile.objects.create(user=u, role=role, assigned_regions=list(regions))
    p.sync_farms_from_regions()
    c = APIClient()
    r = c.post("/api/auth/login/", {"username": username, "password": "pass12345"}, format="json")
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


def farm(code, region="Zone-A"):
    return Farm.objects.create(farm_code=code, name=f"Farm {code}", owner_name="o", region=region, capacity=9000)


def flock(f, age=20, chicks=5000, feed_bags=200):
    fl = Flock.objects.create(farm=f, placement_date=T - D(days=age), chick_count=chicks)
    if feed_bags:
        FeedOrder.objects.create(farm=f, flock=fl, feed_type="BFP", quantity_bags=feed_bags, status="delivered")
    return fl


def entry(fl, day, mort=0, feed=0, weight=None):
    return DailyEntry.objects.create(flock=fl, date=day, mortality_count=mort, feed_bags={'BFP': Decimal(feed)},
                                     avg_body_weight_grams=weight)


@pytest.fixture
def admin(db):
    return client_for("boss", "admin")


def rows(c):
    return {r["farm_code"]: r for r in c.get("/api/dashboard/").data["flock_rows"]}


def test_next_action_for_each_situation(admin):
    ok = flock(farm("OK"))
    entry(ok, T, mort=2, feed=5)
    due = flock(farm("DUE"))
    entry(due, T - D(days=1), feed=5)
    late = flock(farm("LATE"))
    entry(late, T - D(days=4), feed=5)
    sold = flock(farm("SOLD"), chicks=100)
    entry(sold, T, mort=0)
    Sale.objects.create(flock=sold, date=T, bird_count=100, total_weight_kg=Decimal("220"), trader_name="t")
    hungry = flock(farm("FEED"), feed_bags=4)
    entry(hungry, T, feed=2)
    r = rows(admin)
    assert r["OK"]["next_action"] == {"code": "ok", "label": "On track", "severity": "ok"}
    assert r["DUE"]["next_action"]["label"] == "Daily entry due"
    assert r["LATE"]["next_action"] == {"code": "entry", "label": "No entry for 4 days", "severity": "danger"}
    assert r["SOLD"]["next_action"]["code"] == "bill"
    assert r["FEED"]["next_action"]["code"] == "feed"
    order = [x["farm_code"] for x in admin.get("/api/dashboard/").data["flock_rows"]]
    assert order[0] == "LATE" and order[-1] == "OK"                     # worst first


def test_entries_feed_orders_and_figures(admin):
    a = flock(farm("A"), feed_bags=100)
    entry(a, T, feed=10, weight=Decimal("700"))
    b = flock(farm("B"), age=0, feed_bags=50)                          # placed today: no entry due
    FeedOrder.objects.create(farm=b.farm, flock=b, feed_type="BSC", quantity_bags=30)
    d = admin.get("/api/dashboard/").data
    assert d["entries_today"] == {"done": 1, "due": 1}
    assert d["feed_on_farms_bags"] == 140.0
    assert d["pending_orders"] == {"count": 1, "bags": 30}
    ra = {r["farm_code"]: r for r in d["flock_rows"]}["A"]
    assert ra["weight_pct"] is not None and ra["live_birds"] == 5000 and ra["entry_today"] is True


def test_fourteen_day_trend(admin):
    fl = flock(farm("A"), age=30)
    entry(fl, T, mort=3, feed=4)
    entry(fl, T - D(days=5), mort=7, feed=6)
    entry(fl, T - D(days=20), mort=99, feed=9)                         # outside the window
    t = admin.get("/api/dashboard/").data["trend"]
    assert len(t["dates"]) == 14 and t["dates"][-1] == str(T)
    assert t["mortality"][-1] == 3 and t["mortality"][-6] == 7 and sum(t["mortality"]) == 10
    assert t["feed_bags"][-1] == 4.0


def test_regions_and_idle_farms_scoped_to_the_user(db):
    a1, a2, b1 = farm("A1"), farm("A2"), farm("B1", region="Zone-B")
    entry(flock(a1, chicks=1000), T, mort=10)
    entry(flock(b1, chicks=2000), T, mort=2)
    sup = client_for("ravi", "supervisor", ["Zone-A"])
    d = sup.get("/api/dashboard/").data
    assert [r["region"] for r in d["regions"]] == ["Zone-A"]
    za = d["regions"][0]
    assert za["farms"] == 1 and za["flocks"] == 1 and za["live_birds"] == 990 and za["mortality_pct"] == 1.0
    assert [f["farm_code"] for f in d["idle_farms"]] == ["A2"]
    assert [r["farm_code"] for r in d["flock_rows"]] == ["A1"]
