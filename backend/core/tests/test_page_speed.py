"""Page speed: list pages must not run more queries as farms are added, and the
fast ("primed") flock figures must equal the one-query-each figures."""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.billing import generate_bill
from core.models import BillConfig, DailyEntry, Farm, FeedOrder, FeedTransfer, Flock, Medication, Sale
from core.prime import prime_flocks, unprime

pytestmark = pytest.mark.django_db
T = datetime.date.today()
D = datetime.timedelta


def make_farm(tag, i, age=30):
    farm = Farm.objects.create(farm_code=f"{tag}{i}", name=f"Farm {tag}{i}", owner_name="o", region="Zone-A",
                               capacity=9000)
    fl = Flock.objects.create(farm=farm, placement_date=T - D(days=age), chick_count=5000)
    FeedOrder.objects.create(farm=farm, flock=fl, feed_type="BFP", quantity_bags=100, status="delivered")
    FeedOrder.objects.create(farm=farm, flock=fl, feed_type="BSC", quantity_bags=10)
    for d in range(1, 4):
        DailyEntry.objects.create(flock=fl, date=fl.placement_date + D(days=d), mortality_count=2, cull_count=1,
                                  feed_bfp_bags=Decimal("3"), avg_body_weight_grams=500,
                                  water_consumed_liters=Decimal("800" if d == 2 else "300"))
    DailyEntry.objects.create(flock=fl, date=T, mortality_count=30)
    Sale.objects.create(flock=fl, date=T, bird_count=10, total_weight_kg=Decimal("20"), rate_per_kg=Decimal("100"),
                        trader_name="x")
    Medication.objects.create(flock=fl, name="m", date=T, cost=Decimal("10"))
    return fl


PAGES = ["/api/dashboard/", "/api/farms/", "/api/flocks/", "/api/reports/owner-dashboard/",
         "/api/reports/till-date/", "/api/feed-stock/", "/api/feed-orders/", "/api/reports/feed-forecast/",
         "/api/reports/break-even/", "/api/reports/feed-audit/"]


@pytest.mark.parametrize("url", PAGES)
def test_queries_do_not_grow_with_farms(auth_admin, url):
    def count():
        with CaptureQueriesContext(connection) as c:
            r = auth_admin.get(url)
        assert r.status_code == 200, (url, r.status_code)
        return len(c)
    for i in range(2):
        make_farm("a", i)
    small = count()
    for i in range(10):
        make_farm("b", i)
    big = count()
    assert big <= small, f"{url}: {small} queries for 2 farms but {big} for 12"


FIGURES = ["total_mortality", "total_culls", "cull_percentage", "total_feed_kg", "feed_by_type",
           "feed_schedule_status", "total_sold_birds", "total_sold_weight_kg", "mortality_percentage",
           "livability_percentage", "live_birds", "reconciliation", "weight_vs_standard", "scorecard",
           "water_alerts", "fcr", "avg_sold_weight_kg", "epef", "total_medication_cost", "flock_feed_stock",
           "feed_reconciliation"]


def test_primed_figures_equal_unprimed_figures(db):
    BillConfig.get_active()
    flocks = [make_farm("p", i, age=20 + i * 9) for i in range(3)]
    empty = Flock.objects.create(farm=flocks[0].farm, placement_date=T, chick_count=100)   # no data at all
    DailyEntry.objects.filter(flock=flocks[1]).first().delete()                           # Recycle Bin
    FeedTransfer.objects.create(from_farm=flocks[1].farm, to_farm=flocks[2].farm, from_flock=flocks[1],
                                to_flock=flocks[2], feed_type="BFP", quantity_bags=7, date=T)
    closed = flocks[2]
    Sale.objects.create(flock=closed, date=T, bird_count=closed.live_birds, total_weight_kg=Decimal("9000"),
                        rate_per_kg=Decimal("99"), trader_name="t")
    closed.status = "closed"
    closed.save()
    generate_bill(closed, User.objects.create_superuser("boss", password="x"))

    ids = [f.id for f in flocks] + [empty.id]
    slow = {f.id: f for f in Flock.objects.filter(id__in=ids)}
    fast = {f.id: f for f in prime_flocks(Flock.objects.filter(id__in=ids))}
    for fid in ids:
        assert fast[fid]._stats is not None
        for name in FIGURES:
            assert getattr(fast[fid], name) == getattr(slow[fid], name), (fid, name)


def test_primed_figures_need_no_queries_and_unprime_restores_live_reads(db):
    fl = make_farm("q", 0)
    [fast] = prime_flocks([Flock.objects.get(pk=fl.pk)])
    with CaptureQueriesContext(connection) as c:
        for name in FIGURES:
            getattr(fast, name)
    assert len(c) == 0
    unprime([fast])
    before = fast.total_mortality
    DailyEntry.objects.create(flock=fl, date=T - D(days=1), mortality_count=5)
    assert fast.total_mortality == before + 5               # not primed → reads the database again


def test_saving_an_entry_returns_up_to_date_flock_figures(auth_admin):
    fl = make_farm("w", 0)
    before = auth_admin.get(f"/api/flocks/{fl.id}/").data["total_mortality"]
    r = auth_admin.post("/api/daily-entries/", {"flock": fl.id, "date": str(T - D(days=1)), "mortality_count": 7},
                        format="json")
    assert r.status_code == 201, r.data
    assert auth_admin.get(f"/api/flocks/{fl.id}/").data["total_mortality"] == before + 7
    listed = auth_admin.get("/api/flocks/").data
    rows = listed["results"] if isinstance(listed, dict) else listed
    assert next(x for x in rows if x["id"] == fl.id)["total_mortality"] == before + 7
