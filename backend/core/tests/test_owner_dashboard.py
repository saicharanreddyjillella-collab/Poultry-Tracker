"""Owner BI dashboard (F4)."""
import datetime
from decimal import Decimal

import pytest

from core.models import DailyEntry, Sale, Farm
from core.billing import generate_bill

pytestmark = pytest.mark.django_db


def _entry(flock, day, mortality=0, bfp=0):
    return DailyEntry.objects.create(
        flock=flock, date=flock.placement_date + datetime.timedelta(days=day),
        mortality_count=mortality, feed_bfp_bags=bfp,
    )


class TestOwnerDashboard:
    def test_requires_auth(self, api):
        assert api.get("/api/reports/owner-dashboard/").status_code in (401, 403)

    def test_overview_counts(self, auth_admin, farm, make_flock):
        make_flock(farm, chicks=1000, status="active", placed_days_ago=10)
        resp = auth_admin.get("/api/reports/owner-dashboard/")
        assert resp.status_code == 200
        o = resp.data["overview"]
        assert o["active_flocks"] == 1
        assert o["total_live_birds"] == 1000
        assert o["total_farms"] >= 1

    def test_active_cycle_rows(self, auth_admin, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=15)
        _entry(f, 14, mortality=20)
        resp = auth_admin.get("/api/reports/owner-dashboard/")
        rows = resp.data["active_cycle"]
        assert len(rows) == 1
        assert rows[0]["flock_id"] == f.id
        assert rows[0]["age_days"] == 15
        assert "rating" in rows[0]

    def test_alert_population_mismatch(self, auth_admin, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=10)
        _entry(f, 1, mortality=200)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=900, total_weight_kg=Decimal("1800"))
        resp = auth_admin.get("/api/reports/owner-dashboard/")
        cats = [a["category"] for a in resp.data["alerts"] if a["flock_id"] == f.id]
        assert "population" in cats

    def test_alert_stale_data(self, auth_admin, farm, make_flock):
        # active flock with no daily entries at all -> stale
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=10)
        resp = auth_admin.get("/api/reports/owner-dashboard/")
        cats = [a["category"] for a in resp.data["alerts"] if a["flock_id"] == f.id]
        assert "stale_data" in cats

    def test_leaderboard_and_region_from_closed_bills(self, auth_admin, farm, make_flock, config):
        # a closed, billed flock appears in leaderboard + region summary
        f = make_flock(farm, chicks=1000, status="closed", placed_days_ago=42)
        _entry(f, 2, mortality=50, bfp=40)
        Sale.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=40),
                            bird_count=950, total_weight_kg=Decimal("1900"), rate_per_kg=Decimal("100"))
        generate_bill(f)
        resp = auth_admin.get("/api/reports/owner-dashboard/")
        assert resp.data["overview"]["closed_in_period"] == 1
        assert len(resp.data["leaderboard"]["top"]) == 1
        assert resp.data["leaderboard"]["top"][0]["flock_id"] == f.id
        regions = [r["region"] for r in resp.data["region_summary"]]
        assert farm.region in regions

    def test_period_filter_excludes_old_bills(self, auth_admin, farm, make_flock, config):
        f = make_flock(farm, chicks=1000, status="closed", placed_days_ago=400)
        _entry(f, 2, mortality=50, bfp=40)
        Sale.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=40),
                            bird_count=950, total_weight_kg=Decimal("1900"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        # force the bill's generated_at into the past
        from core.models import Bill
        from django.utils import timezone
        Bill.objects.filter(id=bill.id).update(
            generated_at=timezone.now() - datetime.timedelta(days=300))
        resp = auth_admin.get("/api/reports/owner-dashboard/?period_days=90")
        assert resp.data["overview"]["closed_in_period"] == 0
