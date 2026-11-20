"""Feed leakage detector: bag counts (who may record/change them) and the audit flags."""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from core.billing import generate_bill
from core.feed_audit import book_stock_for, run_audit
from core.models import (BillConfig, DailyEntry, Farm, FeedOrder, FeedStockCount, FeedTransfer, Flock,
                         UserProfile)

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


def make_flock(code, region="Zone-A", age=20, chicks=1000, status="active"):
    farm = Farm.objects.create(farm_code=code, name=f"Farm {code}", owner_name="o", region=region, capacity=5000)
    return Flock.objects.create(farm=farm, placement_date=T - D(days=age), chick_count=chicks, status=status)


def deliver(flock, bags, ft="BFP"):
    FeedOrder.objects.create(farm=flock.farm, flock=flock, feed_type=ft, quantity_bags=bags, status="delivered")


def feed(flock, day_no, bags, ft="bfp", weight=None, mort=0):
    return DailyEntry.objects.create(flock=flock, date=flock.placement_date + D(days=day_no),
                                     mortality_count=mort, feed_bags={ft.upper(): bags},
                                     avg_body_weight_grams=weight)


def count(flock, bfp, day=None, bpsc=0, bsc=0):
    return FeedStockCount.objects.create(flock=flock, date=day or T, bags={'BFP': bfp, 'BPSC': bpsc, 'BSC': bsc})


def row_for(flock):
    return next(r for r in run_audit(Flock.objects.select_related("farm").all())["rows"] if r["flock_id"] == flock.id)


def codes(flock):
    return [f["code"] for f in row_for(flock)["flags"]]


@pytest.fixture
def world(db):
    BillConfig.get_active()
    fa = make_flock("A1")
    fb = make_flock("B1", region="Zone-B")
    deliver(fa, 100)
    return {"fa": fa, "fb": fb,
            "admin": client_for("boss", "admin"),
            "supA": client_for("supa", "supervisor", ["Zone-A"]),
            "plant": client_for("mill", "plant")}


# ── paper stock ──────────────────────────────────────────────────────────────

def test_book_stock_counts_deliveries_transfers_and_feeding_up_to_a_date(world):
    fa, fb = world["fa"], world["fb"]
    deliver(fa, 40, "BSC")
    feed(fa, 2, 10)
    feed(fa, 5, 7)
    FeedTransfer.objects.create(from_farm=fa.farm, to_farm=fb.farm, from_flock=fa, to_flock=fb,
                                feed_type="BFP", quantity_bags=20, date=fa.placement_date + D(days=4))
    assert book_stock_for(fa, fa.placement_date + D(days=3))["BFP"] == 90       # 100 − 10
    later = book_stock_for(fa, fa.placement_date + D(days=5))
    assert later["BFP"] == 63 and later["BSC"] == 40 and later["total"] == 103   # 100 − 10 − 20 − 7
    assert book_stock_for(fb)["BFP"] == 20


# ── recording counts ─────────────────────────────────────────────────────────

def test_supervisor_records_a_count_and_sees_the_gap(world):
    fa = world["fa"]
    feed(fa, 1, 30)
    r = world["supA"].post("/api/feed-counts/", {"flock": fa.id, "date": str(T), "bags": {"BFP": 60}}, format="json")
    assert r.status_code == 201, r.data
    assert r.data["book"]["total"] == 70 and r.data["gap_bags"] == 10
    assert r.data["counted_by_name"] == "supa"
    rows = world["supA"].get(f"/api/feed-counts/?flock={fa.id}").data
    assert [x["gap_bags"] for x in rows] == [10]


@pytest.mark.parametrize("who,expected", [("plant", 403), ("supA", 201)])
def test_counts_by_role(world, who, expected):
    """Feed mill can't count bags; any supervisor can, on any farm (covering for a colleague)."""
    flock = world["fb"] if who == "supA" else world["fa"]
    r = world[who].post("/api/feed-counts/", {"flock": flock.id, "date": str(T), "bags": {"BFP": 1}}, format="json")
    assert r.status_code == expected


def test_other_regions_counts_are_visible(world):
    count(world["fb"], 5)
    assert len(world["supA"].get(f"/api/feed-counts/?flock={world['fb'].id}").data) == 1


@pytest.mark.parametrize("body,field", [
    ({"date": str(T + D(days=1))}, "date"),
    ({"date": str(T - D(days=30))}, "date"),                   # before placement (age 20)
])
def test_bad_dates_are_explained(world, body, field):
    r = world["supA"].post("/api/feed-counts/", {"flock": world["fa"].id, "bags": {"BFP": 1}, **body}, format="json")
    assert r.status_code == 400 and field in r.data


def test_one_count_per_day(world):
    count(world["fa"], 5)
    r = world["supA"].post("/api/feed-counts/", {"flock": world["fa"].id, "date": str(T), "bags": {"BFP": 1}},
                           format="json")
    assert r.status_code == 400 and "already exists" in str(r.data["date"])


def test_no_new_counts_on_a_closed_flock(world):
    fa = world["fa"]
    fa.status = "closed"
    fa.save()
    r = world["admin"].post("/api/feed-counts/", {"flock": fa.id, "date": str(T), "bags": {"BFP": 1}}, format="json")
    assert r.status_code == 400 and "active" in str(r.data)


def test_only_admin_changes_or_removes_a_count(world):
    c = count(world["fa"], 50)
    sup = world["supA"]
    assert sup.patch(f"/api/feed-counts/{c.id}/", {"bags": {"BFP": 99}}, format="json").status_code == 403
    assert sup.delete(f"/api/feed-counts/{c.id}/").status_code == 403
    r = world["admin"].patch(f"/api/feed-counts/{c.id}/", {"bags": {"BFP": 99}}, format="json")
    assert r.status_code == 200 and r.data["bags"] == {"BFP": 99}
    assert world["admin"].delete(f"/api/feed-counts/{c.id}/").status_code == 204


def test_counts_on_a_billed_flock_are_locked(world):
    fa = world["fa"]
    feed(fa, 1, 5)
    c = count(fa, 95)
    fa.status = "closed"
    fa.save()
    generate_bill(fa, User.objects.get(username="boss"))
    assert world["admin"].patch(f"/api/feed-counts/{c.id}/", {"bags": {"BFP": 1}}, format="json").status_code == 409


# ── audit flags ──────────────────────────────────────────────────────────────

def test_short_count_is_a_high_flag_with_rupee_value(world):
    fa = world["fa"]
    feed(fa, 1, 30)
    count(fa, 60)                                    # paper 70 → 10 short
    row = row_for(fa)
    f = row["flags"][0]
    assert f["code"] == "COUNT_SHORT" and f["severity"] == "high" and f["bags"] == 10
    cost = float(BillConfig.get_active().feed_cost_per_kg)
    assert row["value_at_risk"] == round(10 * 50 * cost)


def test_tiny_gap_is_counting_noise(world):
    feed(world["fa"], 1, 30)
    count(world["fa"], 69)                           # 1 bag off: below the 2-bag minimum
    assert "COUNT_SHORT" not in codes(world["fa"])


def test_more_bags_than_paper_means_feeding_recorded_that_did_not_happen(world):
    feed(world["fa"], 1, 30)
    count(world["fa"], 80)
    f = row_for(world["fa"])["flags"][0]
    assert f["code"] == "COUNT_EXCESS" and f["severity"] == "medium" and f["bags"] == 10


def test_feed_far_above_standard_with_low_weight_is_flagged(world):
    fa = world["fa"]                                 # 1000 birds, 20 days: standard ≈ 1,190 kg
    deliver(fa, 100)
    for d in range(1, 20):
        feed(fa, d, 2)                               # 38 bags = 1,900 kg recorded
    feed(fa, 20, 2, weight=600)                      # standard at day 20 is 772 g → 78%
    f = next(f for f in row_for(fa)["flags"] if f["code"] == "OVER_STANDARD")
    assert f["severity"] == "high" and "% of standard weight" in f["message"]


def test_heavy_birds_explain_heavy_feeding(world):
    fa = world["fa"]
    deliver(fa, 100)
    for d in range(1, 20):
        feed(fa, d, 2)
    feed(fa, 20, 2, weight=800)                      # above standard → not a leak signal
    assert "OVER_STANDARD" not in codes(fa)


def test_feeding_close_to_standard_is_not_flagged(world):
    fa = world["fa"]                                 # ≈ 1,190 kg standard ≈ 24 bags
    for d in range(1, 21):
        feed(fa, d, 1 if d % 6 else 2)
    count(fa, book_stock_for(fa)["total"])
    assert codes(fa) == []


def test_feed_left_at_close_is_flagged(world):
    fa = world["fa"]
    feed(fa, 1, 90)
    fa.status = "closed"
    fa.save()
    f = row_for(fa)["flags"][0]
    assert f["code"] == "LEFT_AT_CLOSE" and f["bags"] == 10


def test_count_due_after_a_week_without_one(world):
    fa = world["fa"]
    assert "COUNT_DUE" in codes(fa)                  # never counted
    count(fa, 100, day=T - D(days=3))
    assert "COUNT_DUE" not in codes(fa)
    FeedStockCount.objects.all().delete()
    count(fa, 100, day=T - D(days=9))
    msg = next(f for f in row_for(fa)["flags"] if f["code"] == "COUNT_DUE")["message"]
    assert "9 days ago" in msg


def test_young_flocks_are_not_nagged(world):
    young = make_flock("Y1", age=3)
    assert codes(young) == []


# ── report ───────────────────────────────────────────────────────────────────

def test_report_is_admin_only(world):
    assert world["supA"].get("/api/reports/feed-audit/").status_code == 403
    assert world["plant"].get("/api/reports/feed-audit/").status_code == 403
    r = world["admin"].get("/api/reports/feed-audit/")
    assert r.status_code == 200 and r.data["summary"]["flocks_checked"] == 2


def test_report_sorts_worst_first_and_sums_money(world):
    fa = world["fa"]
    feed(fa, 1, 30)
    count(fa, 50)                                    # 20 short
    r = world["admin"].get("/api/reports/feed-audit/").data
    assert r["rows"][0]["flock_id"] == fa.id and r["summary"]["high"] == 1
    assert r["summary"]["value_at_risk"] == r["rows"][0]["value_at_risk"] > 0


def test_report_by_region_and_skips_old_closed_flocks(world):
    old = make_flock("OLD", age=120, status="closed")
    DailyEntry.objects.create(flock=old, date=old.placement_date + D(days=1), feed_bags={'BFP': 1})
    rows = world["admin"].get("/api/reports/feed-audit/?region=Zone-B").data["rows"]
    assert [x["farm_code"] for x in rows] == ["B1"]
    all_codes = [x["farm_code"] for x in world["admin"].get("/api/reports/feed-audit/").data["rows"]]
    assert "OLD" not in all_codes


def test_report_query_count_does_not_grow_with_flocks(world):
    def measure():
        with CaptureQueriesContext(connection) as c:
            assert world["admin"].get("/api/reports/feed-audit/").status_code == 200
        return len(c)
    small = measure()
    for i in range(12):
        f = make_flock(f"X{i}")
        deliver(f, 50)
        feed(f, 1, 3)
        count(f, 40)
    assert measure() == small
