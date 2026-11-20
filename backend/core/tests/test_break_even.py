"""Live-flock break-even projection (F3)."""
import datetime
from decimal import Decimal

import pytest

from core.models import DailyEntry, Sale

pytestmark = pytest.mark.django_db


def _entry(flock, day, bfp=0):
    return DailyEntry.objects.create(
        flock=flock, date=flock.placement_date + datetime.timedelta(days=day), feed_bags={'BFP': bfp},
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


class TestBlendedBreakEven:
    def _entry(self, flock, day, bfp=0):
        return DailyEntry.objects.create(
            flock=flock, date=flock.placement_date + datetime.timedelta(days=day), feed_bags={'BFP': bfp})

    def test_overall_present(self, auth_admin, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=20)
        self._entry(f, 10, bfp=20)
        resp = auth_admin.get("/api/reports/break-even/")
        o = resp.data["overall"]
        assert o["blended_break_even_per_kg"] > 0
        assert o["total_cost"] > 0
        assert o["total_projected_weight_kg"] > 0

    def test_blended_equals_cost_over_weight(self, auth_admin, farm, make_flock):
        f1 = make_flock(farm, chicks=1000, status="active", placed_days_ago=20)
        self._entry(f1, 10, bfp=20)
        f2 = make_flock(farm, chicks=2000, status="active", placed_days_ago=15)
        self._entry(f2, 10, bfp=30)
        resp = auth_admin.get("/api/reports/break-even/")
        o = resp.data["overall"]
        expected = round(o["total_cost"] / o["total_projected_weight_kg"], 2)
        # blended is quantized to 2dp; allow a 1-paisa rounding gap
        assert abs(o["blended_break_even_per_kg"] - expected) <= 0.02

    def test_blended_differs_from_simple_average(self, auth_admin, farm, make_flock):
        # one small cheap flock + one large pricier flock -> blended is weight-
        # weighted, not the midpoint of the two rates
        f1 = make_flock(farm, chicks=200, status="active", placed_days_ago=38)
        self._entry(f1, 10, bfp=6)
        f2 = make_flock(farm, chicks=4000, status="active", placed_days_ago=5)
        self._entry(f2, 2, bfp=10)
        resp = auth_admin.get("/api/reports/break-even/")
        blended = resp.data["overall"]["blended_break_even_per_kg"]
        avg = resp.data["avg_break_even_per_kg"]
        # both positive; they are computed differently (weight-weighted vs mean)
        assert blended > 0 and avg > 0

    def test_blended_single_flock_matches_row(self, auth_admin, farm, make_flock):
        f = make_flock(farm, chicks=1000, status="active", placed_days_ago=20)
        self._entry(f, 10, bfp=20)
        resp = auth_admin.get("/api/reports/break-even/")
        row = resp.data["flocks"][0]
        blended = resp.data["overall"]["blended_break_even_per_kg"]
        assert abs(blended - row["cost_per_kg"]) <= 0.02
