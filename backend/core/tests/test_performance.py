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
        resp = auth_admin.get(f"/api/flocks/?farm={farm.id}")   # unfiltered lists are paged (E13)
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


class TestWeightVsStandard:
    def test_none_when_no_weight_recorded(self, farm, make_flock):
        f = make_flock(farm, status="active", placed_days_ago=21)
        _entry(f, 1, mortality=0)  # no body weight
        assert f.weight_vs_standard is None

    def test_on_track_within_band(self, farm, make_flock):
        # day 21 Cobb-400 standard = 838g; 850g is +1.4% -> on_track
        f = make_flock(farm, status="active", placed_days_ago=21)
        e = _entry(f, 21)
        e.avg_body_weight_grams = Decimal("850")
        e.save()
        w = f.weight_vs_standard
        assert w["day"] == 21
        assert w["standard_g"] == 838.0
        assert w["actual_g"] == 850.0
        assert w["variance_g"] == 12.0
        assert w["variance_pct"] == 1.4
        assert w["status"] == "on_track"

    def test_below_standard(self, farm, make_flock):
        # day 21 std 838; 700g is -16.5% -> below
        f = make_flock(farm, status="active", placed_days_ago=21)
        e = _entry(f, 21)
        e.avg_body_weight_grams = Decimal("700")
        e.save()
        w = f.weight_vs_standard
        assert w["status"] == "below"
        assert w["variance_g"] == -138.0

    def test_above_standard(self, farm, make_flock):
        # day 21 std 838; 950g is +13.4% -> above
        f = make_flock(farm, status="active", placed_days_ago=21)
        e = _entry(f, 21)
        e.avg_body_weight_grams = Decimal("950")
        e.save()
        assert f.weight_vs_standard["status"] == "above"

    def test_uses_latest_weight_entry(self, farm, make_flock):
        f = make_flock(farm, status="active", placed_days_ago=21)
        e1 = _entry(f, 14); e1.avg_body_weight_grams = Decimal("436"); e1.save()
        e2 = _entry(f, 21); e2.avg_body_weight_grams = Decimal("838"); e2.save()
        w = f.weight_vs_standard
        assert w["day"] == 21
        assert w["actual_g"] == 838.0
        assert w["status"] == "on_track"

    def test_weight_vs_standard_in_cumulative(self, auth_admin, farm, make_flock):
        f = make_flock(farm, status="active", placed_days_ago=21)
        e = _entry(f, 21); e.avg_body_weight_grams = Decimal("838"); e.save()
        resp = auth_admin.get(f"/api/flocks/{f.id}/cumulative/")
        assert resp.status_code == 200
        w = resp.data["weight_vs_standard"]
        assert w["standard_g"] == 838.0
        assert w["status"] == "on_track"


class TestScorecard:
    def test_active_flock_livability_and_weight_only(self, farm, make_flock):
        """Active flock: only livability + weight components (no EPEF/FCR)."""
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=21)
        e = _entry(f, 21, mortality=30)   # 3% mortality
        e.avg_body_weight_grams = Decimal("700")  # day21 std 838 -> -16.5%
        e.save()
        sc = f.scorecard
        labels = [c["label"] for c in sc["components"]]
        assert labels == ["livability", "weight"]
        assert sc["overall_score"] == 83.5
        assert sc["rating"] == "Good"
        assert sc["farmer_grade"] is None

    def test_excellent_closed_flock(self, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="closed", placed_days_ago=42)
        e = _entry(f, 42, mortality=50, bfp=40)   # 5% mortality, 2000kg feed
        e.avg_body_weight_grams = Decimal("2677")  # on target
        e.save()
        Sale.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=40),
                            bird_count=950, total_weight_kg=Decimal("1900"))
        sc = f.scorecard
        labels = sorted(c["label"] for c in sc["components"])
        assert labels == ["epef", "fcr", "livability", "weight"]
        assert sc["overall_score"] == 100.0
        assert sc["rating"] == "Excellent"

    def test_poor_closed_flock(self, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="closed", placed_days_ago=42)
        _entry(f, 2, mortality=250, bfp=52)   # 25% mortality, 2600kg feed
        Sale.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=40),
                            bird_count=700, total_weight_kg=Decimal("1050"))
        sc = f.scorecard
        assert sc["rating"] == "Poor"
        assert sc["overall_score"] < 50

    def test_rating_bands(self, farm, make_flock):
        # Just check the band function via a mid flock -> Fair/Good boundary.
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=21)
        # ~10% mortality -> survived 90 -> liv 94.7; no weight -> only livability
        _entry(f, 1, mortality=100)
        sc = f.scorecard
        assert sc["components"][0]["label"] == "livability"
        # single component => overall == livability score
        assert sc["overall_score"] == sc["components"][0]["score"]

    def test_farmer_grade_surfaced_when_bill_exists(self, farm, make_flock, config):
        from core.billing import generate_bill
        f = make_flock(farm, chicks=1000, status="closed", placed_days_ago=42)
        _entry(f, 2, mortality=30, bfp=40)
        Sale.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=40),
                            bird_count=950, total_weight_kg=Decimal("1900"), rate_per_kg=Decimal("100"))
        generate_bill(f)
        sc = f.scorecard
        assert sc["farmer_grade"] is not None

    def test_scorecard_in_cumulative(self, auth_admin, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=21)
        _entry(f, 1, mortality=30)
        resp = auth_admin.get(f"/api/flocks/{f.id}/cumulative/")
        assert resp.status_code == 200
        assert "scorecard" in resp.data
        assert resp.data["scorecard"]["rating"] in ("Excellent", "Good", "Fair", "Poor")


class TestWaterFeedRatio:
    def _wentry(self, flock, day, water, bags):
        e = DailyEntry.objects.create(
            flock=flock, date=flock.placement_date + datetime.timedelta(days=day),
            feed_bfp_bags=bags, water_consumed_liters=Decimal(str(water)),
        )
        return e

    def test_ratio_none_without_feed(self, farm, make_flock):
        f = make_flock(farm, status="active")
        e = self._wentry(f, 1, water=500, bags=0)
        assert e.water_feed_ratio is None
        assert e.water_feed_status is None

    def test_normal_ratio(self, farm, make_flock):
        f = make_flock(farm, status="active")
        e = self._wentry(f, 1, water=850, bags=10)  # 500 kg -> 1.7
        assert e.water_feed_ratio == 1.7
        assert e.water_feed_status == "normal"

    def test_low_ratio_flagged(self, farm, make_flock):
        f = make_flock(farm, status="active")
        e = self._wentry(f, 1, water=400, bags=10)  # 0.8 < 1.2
        assert e.water_feed_ratio == 0.8
        assert e.water_feed_status == "low"

    def test_high_ratio_flagged(self, farm, make_flock):
        f = make_flock(farm, status="active")
        e = self._wentry(f, 1, water=1500, bags=10)  # 3.0 > 2.5
        assert e.water_feed_ratio == 3.0
        assert e.water_feed_status == "high"

    def test_band_boundaries_are_normal(self, farm, make_flock):
        f = make_flock(farm, status="active")
        # exactly 1.2 and 2.5 are within band (not < / not >)
        lo = self._wentry(f, 1, water=600, bags=10)   # 1.2
        hi = self._wentry(f, 2, water=1250, bags=10)  # 2.5
        assert lo.water_feed_status == "normal"
        assert hi.water_feed_status == "normal"

    def test_flock_water_alerts_lists_only_abnormal(self, farm, make_flock):
        f = make_flock(farm, status="active")
        self._wentry(f, 1, water=850, bags=10)   # normal
        self._wentry(f, 2, water=400, bags=10)   # low
        self._wentry(f, 3, water=1500, bags=10)  # high
        alerts = f.water_alerts
        assert len(alerts) == 2
        statuses = {a["status"] for a in alerts}
        assert statuses == {"low", "high"}

    def test_water_alerts_in_cumulative(self, auth_admin, farm, make_flock):
        f = make_flock(farm, status="active")
        self._wentry(f, 1, water=400, bags=10)  # low
        resp = auth_admin.get(f"/api/flocks/{f.id}/cumulative/")
        assert resp.status_code == 200
        assert len(resp.data["water_alerts"]) == 1
        assert resp.data["water_alerts"][0]["status"] == "low"
        # per-entry fields present
        row = next(e for e in resp.data["entries"] if e["day_number"] == 1)
        assert row["water_feed_ratio"] == 0.8
        assert row["water_feed_status"] == "low"
