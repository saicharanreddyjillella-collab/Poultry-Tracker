"""Feed-lot reconciliation (1.2): dispatched vs consumed, variance flags."""
import datetime
from decimal import Decimal

import pytest

from core.models import DailyEntry, FeedOrder, FeedTransfer, Farm, BillConfig

pytestmark = pytest.mark.django_db


def _consume(flock, day, bpsc=0, bsc=0, bfp=0):
    return DailyEntry.objects.create(
        flock=flock, date=flock.placement_date + datetime.timedelta(days=day),
        feed_bpsc_bags=bpsc, feed_bsc_bags=bsc, feed_bfp_bags=bfp,
    )


def _dispatch(farm, flock, feed_type, bags, status="delivered"):
    return FeedOrder.objects.create(
        farm=farm, flock=flock, feed_type=feed_type, quantity_bags=bags, status=status,
    )


class TestFeedReconciliation:
    def test_balanced_when_dispatch_equals_consumed(self, farm, make_flock):
        f = make_flock(farm, status="active")
        _dispatch(farm, f, "BFP", 40)
        _consume(f, 1, bfp=40)
        r = f.feed_reconciliation
        assert r["dispatched_bags"] == 40
        assert r["consumed_bags"] == 40
        assert r["variance_bags"] == 0
        assert r["is_balanced"] is True
        assert r["status"] == "balanced"

    def test_over_dispatched_flagged(self, farm, make_flock):
        """Much more dispatched than fed -> possible diversion."""
        f = make_flock(farm, status="active")
        _dispatch(farm, f, "BFP", 100)
        _consume(f, 1, bfp=40)   # 60 bags unaccounted
        r = f.feed_reconciliation
        assert r["variance_bags"] == 60
        assert r["variance_pct"] == 60.0
        assert r["status"] == "over_dispatched"
        assert r["is_balanced"] is False

    def test_under_dispatched_flagged(self, farm, make_flock):
        """More fed than dispatched -> under-recorded dispatch / under-fill."""
        f = make_flock(farm, status="active")
        _dispatch(farm, f, "BFP", 40)
        _consume(f, 1, bfp=60)   # fed 20 more than dispatched
        r = f.feed_reconciliation
        assert r["variance_bags"] == -20
        assert r["status"] == "under_dispatched"
        assert r["is_balanced"] is False

    def test_within_tolerance_is_balanced(self, farm, make_flock):
        """5% default tolerance: 100 dispatched, 97 fed -> 3% -> balanced."""
        f = make_flock(farm, status="active")
        _dispatch(farm, f, "BFP", 100)
        _consume(f, 1, bfp=97)
        r = f.feed_reconciliation
        assert r["variance_pct"] == 3.0
        assert r["is_balanced"] is True

    def test_pending_orders_not_counted_as_dispatched(self, farm, make_flock):
        f = make_flock(farm, status="active")
        _dispatch(farm, f, "BFP", 40, status="delivered")
        _dispatch(farm, f, "BFP", 20, status="pending")   # not yet delivered
        _consume(f, 1, bfp=40)
        r = f.feed_reconciliation
        assert r["dispatched_bags"] == 40  # pending excluded

    def test_per_type_breakdown(self, farm, make_flock):
        f = make_flock(farm, status="active")
        _dispatch(farm, f, "BPSC", 10)
        _dispatch(farm, f, "BFP", 30)
        _consume(f, 1, bpsc=10, bfp=25)
        bt = f.feed_reconciliation["by_type"]
        assert bt["BPSC"] == {"dispatched": 10, "consumed": 10, "variance": 0}
        assert bt["BFP"] == {"dispatched": 30, "consumed": 25, "variance": 5}

    def test_transfers_adjust_dispatched(self, farm, make_flock):
        f = make_flock(farm, status="active")
        other = make_flock(farm, status="active")
        _dispatch(farm, f, "BFP", 40)
        # transfer 10 bags out of f to other
        FeedTransfer.objects.create(from_farm=farm, to_farm=farm,
                                    from_flock=f, to_flock=other,
                                    feed_type="BFP", quantity_bags=10,
                                    date=f.placement_date)
        _consume(f, 1, bfp=30)
        r = f.feed_reconciliation
        assert r["dispatched_bags"] == 30   # 40 delivered - 10 transferred out
        assert r["is_balanced"] is True

    def test_tolerance_config_respected(self, farm, make_flock):
        cfg = BillConfig.get_active()
        cfg.feed_reconciliation_tolerance_pct = Decimal("10")
        cfg.save()
        f = make_flock(farm, status="active")
        _dispatch(farm, f, "BFP", 100)
        _consume(f, 1, bfp=92)   # 8% variance, within 10% tolerance
        assert f.feed_reconciliation["is_balanced"] is True

    def test_feed_recon_in_cumulative(self, auth_admin, farm, make_flock):
        f = make_flock(farm, status="active")
        _dispatch(farm, f, "BFP", 100)
        _consume(f, 1, bfp=40)
        resp = auth_admin.get(f"/api/flocks/{f.id}/cumulative/")
        assert resp.status_code == 200
        fr = resp.data["feed_reconciliation"]
        assert fr["status"] == "over_dispatched"
        assert fr["variance_bags"] == 60
