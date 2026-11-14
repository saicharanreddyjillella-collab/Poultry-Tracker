"""Feed requirement forecast (F1)."""
import datetime
from decimal import Decimal

import pytest

from core.standards import get_daily_feed_intake, get_feed_phase

pytestmark = pytest.mark.django_db


class TestIntakeCurve:
    def test_intake_increases_with_age(self):
        assert get_daily_feed_intake(1) < get_daily_feed_intake(21) < get_daily_feed_intake(42)

    def test_intake_clamps(self):
        assert get_daily_feed_intake(-5) == get_daily_feed_intake(0)
        assert get_daily_feed_intake(999) == get_daily_feed_intake(56)

    def test_intake_interpolates(self):
        # a day not in the table returns something between its neighbours
        v = get_daily_feed_intake(21)
        assert v > 0

    def test_feed_phase_by_age(self):
        assert get_feed_phase(5) == 'BPSC'
        assert get_feed_phase(15) == 'BSC'
        assert get_feed_phase(30) == 'BFP'


class TestFeedForecastApi:
    def test_forecast_for_active_flock(self, auth_admin, farm, make_flock):
        # flock placed 10 days ago, 1000 birds, active
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=10)
        resp = auth_admin.get("/api/reports/feed-forecast/")
        assert resp.status_code == 200
        d = resp.data
        assert d["weeks"] == 4
        assert d["active_flocks"] == 1
        assert len(d["weekly"]) == 4
        assert d["totals"]["total_kg"] > 0
        # weekly totals should sum to the grand total (within rounding)
        wk_sum = sum(w["total_kg"] for w in d["weekly"])
        assert abs(wk_sum - d["totals"]["total_kg"]) < 1.0

    def test_closed_flock_excluded(self, auth_admin, farm, make_flock):
        make_flock(farm, chicks=1000, status="closed", placed_days_ago=42)
        resp = auth_admin.get("/api/reports/feed-forecast/")
        assert resp.data["active_flocks"] == 0
        assert resp.data["totals"]["total_kg"] == 0

    def test_phase_attribution_young_flock(self, auth_admin, farm, make_flock):
        # placed today -> early days are BPSC, so week 1 has BPSC demand
        make_flock(farm, chicks=1000, status="active", placed_days_ago=0)
        resp = auth_admin.get("/api/reports/feed-forecast/")
        wk1 = resp.data["weekly"][0]
        assert wk1["bpsc_kg"] > 0

    def test_weeks_param(self, auth_admin, farm, make_flock):
        make_flock(farm, chicks=1000, status="active", placed_days_ago=5)
        resp = auth_admin.get("/api/reports/feed-forecast/?weeks=2")
        assert resp.data["weeks"] == 2
        assert len(resp.data["weekly"]) == 2

    def test_per_flock_breakdown(self, auth_admin, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=10)
        resp = auth_admin.get("/api/reports/feed-forecast/")
        pf = resp.data["per_flock"]
        assert len(pf) == 1
        assert pf[0]["flock_id"] == f.id
        assert pf[0]["forecast_kg"] > 0

    def test_more_birds_more_feed(self, auth_admin, farm, make_flock):
        make_flock(farm, chicks=500, status="active", placed_days_ago=10)
        small = auth_admin.get("/api/reports/feed-forecast/").data["totals"]["total_kg"]
        make_flock(farm, chicks=4500, status="active", placed_days_ago=10)
        big = auth_admin.get("/api/reports/feed-forecast/").data["totals"]["total_kg"]
        assert big > small

    def test_requires_auth(self, api):
        resp = api.get("/api/reports/feed-forecast/")
        assert resp.status_code in (401, 403)
