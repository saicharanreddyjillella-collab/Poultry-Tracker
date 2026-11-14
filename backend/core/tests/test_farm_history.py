"""Multi-cycle farm performance history (F2)."""
import datetime
from decimal import Decimal

import pytest

from core.models import DailyEntry, Sale, Flock
from core.billing import generate_bill

pytestmark = pytest.mark.django_db


def _entry(flock, day, mortality=0, bfp=0):
    return DailyEntry.objects.create(
        flock=flock, date=flock.placement_date + datetime.timedelta(days=day),
        mortality_count=mortality, feed_bfp_bags=bfp)


def _closed_flock(farm, placed_days_ago, mortality, feed_bags, sold_birds, sold_kg):
    import datetime as dt
    f = Flock.objects.create(
        farm=farm, placement_date=dt.date.today() - dt.timedelta(days=placed_days_ago),
        chick_count=1000, status='closed')
    _entry(f, 2, mortality=mortality, bfp=feed_bags)
    Sale.objects.create(flock=f, date=f.placement_date + dt.timedelta(days=40),
                        bird_count=sold_birds, total_weight_kg=Decimal(str(sold_kg)),
                        rate_per_kg=Decimal("100"))
    generate_bill(f)
    return f


class TestFarmHistory:
    def test_404_missing_farm(self, auth_admin):
        assert auth_admin.get("/api/farms/99999/performance-history/").status_code == 404

    def test_empty_when_no_closed_flocks(self, auth_admin, farm, make_flock):
        make_flock(farm, status="active", placed_days_ago=10)
        resp = auth_admin.get(f"/api/farms/{farm.id}/performance-history/")
        assert resp.status_code == 200
        assert resp.data["cycle_count"] == 0
        assert resp.data["cycles"] == []

    def test_cycles_in_placement_order(self, auth_admin, farm, config):
        # older first
        _closed_flock(farm, placed_days_ago=120, mortality=50, feed_bags=44, sold_birds=950, sold_kg=1800)
        _closed_flock(farm, placed_days_ago=60, mortality=40, feed_bags=42, sold_birds=960, sold_kg=1900)
        resp = auth_admin.get(f"/api/farms/{farm.id}/performance-history/")
        assert resp.data["cycle_count"] == 2
        dates = [c["placement_date"] for c in resp.data["cycles"]]
        assert dates == sorted(dates)
        # each cycle carries metrics
        c0 = resp.data["cycles"][0]
        assert c0["fcr"] is not None and c0["epef"] is not None
        assert c0["grade"] is not None and c0["settlement_paid"] is not None

    def test_averages_computed(self, auth_admin, farm, config):
        _closed_flock(farm, placed_days_ago=120, mortality=50, feed_bags=44, sold_birds=950, sold_kg=1800)
        _closed_flock(farm, placed_days_ago=60, mortality=40, feed_bags=42, sold_birds=960, sold_kg=1900)
        resp = auth_admin.get(f"/api/farms/{farm.id}/performance-history/")
        avg = resp.data["averages"]
        assert avg["fcr"] is not None
        assert avg["livability_pct"] is not None

    def test_trend_improving_epef(self, auth_admin, farm, config):
        # first cycle poor (high FCR/low EPEF), second better -> EPEF improving
        _closed_flock(farm, placed_days_ago=120, mortality=150, feed_bags=52, sold_birds=820, sold_kg=1400)
        _closed_flock(farm, placed_days_ago=60, mortality=40, feed_bags=40, sold_birds=960, sold_kg=1950)
        resp = auth_admin.get(f"/api/farms/{farm.id}/performance-history/")
        assert resp.data["trends"]["epef"] == "improving"

    def test_trend_none_single_cycle(self, auth_admin, farm, config):
        _closed_flock(farm, placed_days_ago=60, mortality=40, feed_bags=42, sold_birds=960, sold_kg=1900)
        resp = auth_admin.get(f"/api/farms/{farm.id}/performance-history/")
        assert resp.data["trends"]["epef"] is None  # need 2+ to trend

    def test_requires_auth(self, api, farm):
        assert api.get(f"/api/farms/{farm.id}/performance-history/").status_code in (401, 403)
