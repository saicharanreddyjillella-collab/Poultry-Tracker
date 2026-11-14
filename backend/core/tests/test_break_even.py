"""Live-flock break-even projection (F3)."""
import datetime
from decimal import Decimal

import pytest

from core.models import DailyEntry, Sale

pytestmark = pytest.mark.django_db


def _entry(flock, day, bfp=0):
    return DailyEntry.objects.create(
        flock=flock, date=flock.placement_date + datetime.timedelta(days=day), feed_bfp_bags=bfp,
    )


class TestBreakEven:
    def test_requires_auth(self, api):
        assert api.get("/api/reports/break-even/").status_code in (401, 403)

    def test_active_flock_projected(self, auth_admin, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=20)
        _entry(f, 10, bfp=20)
        resp = auth_admin.get("/api/reports/break-even/")
        assert resp.status_code == 200
        assert resp.data["active_flocks"] == 1
        row = resp.data["flocks"][0]
        assert row["flock_id"] == f.id
        assert row["cost_per_kg"] > 0
        assert row["break_even_price_per_kg"] == row["cost_per_kg"]
        # feed to finish >= feed consumed
        assert row["feed_to_finish_bags"] >= row["feed_consumed_bags"]

    def test_closed_flock_excluded(self, auth_admin, farm, make_flock):
        make_flock(farm, chicks=1000, status="closed", placed_days_ago=42)
        resp = auth_admin.get("/api/reports/break-even/")
        assert resp.data["active_flocks"] == 0
        assert resp.data["flocks"] == []

    def test_cost_per_kg_in_sane_range(self, auth_admin, farm, make_flock):
        # default rates -> broiler production cost typically ~70-110 /kg
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=25)
        _entry(f, 10, bfp=30)
        resp = auth_admin.get("/api/reports/break-even/")
        c = resp.data["flocks"][0]["cost_per_kg"]
        assert 40 < c < 200

    def test_rates_echoed(self, auth_admin, farm, make_flock, config):
        make_flock(farm, chicks=1000, status="active", placed_days_ago=10)
        resp = auth_admin.get("/api/reports/break-even/")
        assert resp.data["rates"]["feed_cost_per_kg"] == float(config.feed_cost_per_kg)
        assert resp.data["feed_rate_per_kg"] == float(config.feed_cost_per_kg)

    def test_higher_feed_rate_raises_breakeven(self, auth_admin, farm, make_flock, config):
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=20)
        _entry(f, 10, bfp=20)
        base = auth_admin.get("/api/reports/break-even/").data["flocks"][0]["cost_per_kg"]
        config.feed_cost_per_kg = Decimal("60.00"); config.save()
        higher = auth_admin.get("/api/reports/break-even/").data["flocks"][0]["cost_per_kg"]
        assert higher > base

    def test_finish_age_param(self, auth_admin, farm, make_flock):
        make_flock(farm, chicks=1000, status="active", placed_days_ago=20)
        resp = auth_admin.get("/api/reports/break-even/?finish_age=45")
        assert resp.data["finish_age"] == 45

    def test_avg_break_even(self, auth_admin, farm, make_flock):
        f1 = make_flock(farm, chicks=1000, status="active", placed_days_ago=20)
        _entry(f1, 10, bfp=20)
        resp = auth_admin.get("/api/reports/break-even/")
        rows = resp.data["flocks"]
        if rows:
            costs = [r["cost_per_kg"] for r in rows if r["cost_per_kg"] > 0]
            expected = round(sum(costs) / len(costs), 2)
            assert resp.data["avg_break_even_per_kg"] == expected
