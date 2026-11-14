"""Tests for flock performance indices (EPEF and its inputs)."""
import datetime
from decimal import Decimal

import pytest

from core.models import DailyEntry, Sale

pytestmark = pytest.mark.django_db


def _entry(flock, day, mortality=0, bpsc=0, bsc=0, bfp=0):
    return DailyEntry.objects.create(
        flock=flock, date=flock.placement_date + datetime.timedelta(days=day),
        mortality_count=mortality, feed_bpsc_bags=bpsc, feed_bsc_bags=bsc, feed_bfp_bags=bfp,
    )


class TestAvgSoldWeight:
    def test_none_when_no_sales(self, farm, make_flock):
        f = make_flock(farm, status="closed")
        assert f.avg_sold_weight_kg is None

    def test_value(self, farm, make_flock):
        f = make_flock(farm, status="closed")
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=950,
                            total_weight_kg=Decimal("1900"))
        assert f.avg_sold_weight_kg == 2.0


class TestEPEF:
    def test_none_when_active(self, farm, make_flock):
        f = make_flock(farm, status="active", placed_days_ago=42)
        _entry(f, 1, bfp=40)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=950,
                            total_weight_kg=Decimal("1900"))
        # EPEF depends on FCR which is None for active flocks
        assert f.epef is None

    def test_none_when_no_sales(self, farm, make_flock):
        f = make_flock(farm, status="closed", placed_days_ago=42)
        _entry(f, 1, bfp=40)
        assert f.epef is None

    def test_known_value(self, farm, make_flock):
        """1000 chicks, 50 deaths (livability 95%), 42 days, feed 2000kg,
        sell 950 birds @ 1900kg (avg 2.0kg). FCR=1.053.
        EPEF = (95 * 2.0 * 100) / (42 * 1.053) = 429.6
        """
        f = make_flock(farm, chicks=1000, status="closed", placed_days_ago=42)
        _entry(f, 2, mortality=50, bfp=40)   # 40 bags => 2000 kg feed
        Sale.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=40),
                            bird_count=950, total_weight_kg=Decimal("1900"))
        assert f.livability_percentage == 95.0
        assert f.fcr == 1.053
        assert f.avg_sold_weight_kg == 2.0
        assert f.epef == 429.6

    def test_higher_livability_raises_epef(self, farm, make_flock):
        """Same feed/weight/age, fewer deaths -> higher EPEF."""
        base = make_flock(farm, chicks=1000, status="closed", placed_days_ago=42)
        _entry(base, 2, mortality=100, bfp=40)
        Sale.objects.create(flock=base, date=base.placement_date, bird_count=900,
                            total_weight_kg=Decimal("1800"))

        f2 = make_flock(farm, chicks=1000, status="closed", placed_days_ago=42)
        _entry(f2, 2, mortality=20, bfp=40)
        Sale.objects.create(flock=f2, date=f2.placement_date, bird_count=980,
                            total_weight_kg=Decimal("1960"))
        assert f2.epef > base.epef


class TestEPEFApi:
    def test_epef_in_flock_cumulative(self, auth_admin, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="closed", placed_days_ago=42)
        _entry(f, 2, mortality=50, bfp=40)
        Sale.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=40),
                            bird_count=950, total_weight_kg=Decimal("1900"))
        resp = auth_admin.get(f"/api/flocks/{f.id}/cumulative/")
        assert resp.status_code == 200
        assert resp.data["epef"] == 429.6
        assert resp.data["avg_sold_weight_kg"] == 2.0

    def test_epef_null_for_active_in_list(self, auth_admin, farm, make_flock):
        f = make_flock(farm, status="active", placed_days_ago=10)
        resp = auth_admin.get("/api/flocks/")
        assert resp.status_code == 200
        row = next(r for r in resp.data if r["id"] == f.id)
        assert row["epef"] is None


class TestCulling:
    def test_total_culls_zero_default(self, farm, make_flock):
        f = make_flock(farm, status="active")
        assert f.total_culls == 0

    def test_total_culls_sums_entries(self, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active")
        _entry(f, 1, mortality=5)
        DailyEntry.objects.filter(flock=f).update(cull_count=3)
        _entry(f, 2)
        DailyEntry.objects.filter(flock=f, date=f.placement_date + datetime.timedelta(days=2)).update(cull_count=4)
        assert f.total_culls == 7

    def test_culls_separate_from_mortality(self, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active")
        e = _entry(f, 1, mortality=10)
        e.cull_count = 5
        e.save()
        assert f.total_mortality == 10   # deaths only
        assert f.total_culls == 5        # culls only

    def test_cull_percentage(self, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active")
        e = _entry(f, 1)
        e.cull_count = 25
        e.save()
        assert f.cull_percentage == 2.5

    def test_live_birds_subtracts_culls(self, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active")
        e = _entry(f, 1, mortality=50)
        e.cull_count = 20
        e.save()
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=600, total_weight_kg=Decimal("1200"))
        # 1000 - 50 mortality - 20 culls - 600 sold = 330
        assert f.live_birds == 330

    def test_cull_count_accepted_via_api(self, auth_admin, farm, make_flock):
        f = make_flock(farm, status="active")
        resp = auth_admin.post("/api/daily-entries/", {
            "flock": f.id, "date": str(f.placement_date),
            "mortality_count": 4, "cull_count": 6,
        }, format="json")
        assert resp.status_code in (200, 201), resp.data
        f.refresh_from_db()
        assert f.total_mortality == 4
        assert f.total_culls == 6

    def test_culls_in_flock_cumulative(self, auth_admin, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active")
        e = _entry(f, 1, mortality=10)
        e.cull_count = 5
        e.save()
        resp = auth_admin.get(f"/api/flocks/{f.id}/cumulative/")
        assert resp.status_code == 200
        assert resp.data["total_culls"] == 5
        assert resp.data["live_birds"] == 1000 - 10 - 5


class TestReconciliation:
    def test_balanced_normal_flock(self, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active")
        e = _entry(f, 1, mortality=30)
        e.cull_count = 10
        e.save()
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=500,
                            total_weight_kg=Decimal("1000"))
        r = f.reconciliation
        assert r["opening"] == 1000
        assert r["mortality"] == 30
        assert r["culls"] == 10
        assert r["sold"] == 500
        assert r["accounted"] == 540
        assert r["closing"] == 460
        assert r["is_balanced"] is True
        assert r["overcount"] == 0

    def test_closing_matches_live_birds(self, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active")
        e = _entry(f, 1, mortality=50)
        e.cull_count = 25
        e.save()
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=400,
                            total_weight_kg=Decimal("800"))
        assert f.reconciliation["closing"] == f.live_birds

    def test_unbalanced_overcount_flagged(self, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active")
        _entry(f, 1, mortality=200)
        # sell more than remain -> over-accounted
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=900,
                            total_weight_kg=Decimal("1800"))
        r = f.reconciliation
        # 200 + 900 = 1100 accounted vs 1000 placed -> closing -100
        assert r["accounted"] == 1100
        assert r["closing"] == -100
        assert r["is_balanced"] is False
        assert r["overcount"] == 100

    def test_exact_zero_is_balanced(self, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active")
        _entry(f, 1, mortality=100)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=900,
                            total_weight_kg=Decimal("1800"))
        r = f.reconciliation
        assert r["closing"] == 0
        assert r["is_balanced"] is True

    def test_reconciliation_in_flock_cumulative(self, auth_admin, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active")
        _entry(f, 1, mortality=30)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=500,
                            total_weight_kg=Decimal("1000"))
        resp = auth_admin.get(f"/api/flocks/{f.id}/cumulative/")
        assert resp.status_code == 200
        r = resp.data["reconciliation"]
        assert r["closing"] == 470
        assert r["is_balanced"] is True
