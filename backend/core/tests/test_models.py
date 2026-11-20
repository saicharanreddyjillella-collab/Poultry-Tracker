"""Model-level tests: derived properties on Flock / Farm / UserProfile."""
import datetime
from decimal import Decimal

import pytest

from core.models import DailyEntry, Sale, Medication, Flock, Farm, UserProfile
from django.contrib.auth.models import User

pytestmark = pytest.mark.django_db


def _entry(flock, day_offset, mortality=0, bpsc=0, bsc=0, bfp=0):
    return DailyEntry.objects.create(
        flock=flock,
        date=flock.placement_date + datetime.timedelta(days=day_offset),
        mortality_count=mortality,
        feed_bpsc_bags=bpsc, feed_bsc_bags=bsc, feed_bfp_bags=bfp,
    )


class TestFlockAggregates:
    def test_total_mortality_sums_entries(self, farm, make_flock):
        f = make_flock(farm, chicks=1000)
        _entry(f, 1, mortality=5)
        _entry(f, 2, mortality=3)
        assert f.total_mortality == 8

    def test_total_feed_kg_uses_50kg_bags(self, farm, make_flock):
        f = make_flock(farm)
        _entry(f, 1, bpsc=2, bsc=1, bfp=0)  # 3 bags
        _entry(f, 2, bfp=1)                 # 1 bag  -> 4 bags total
        assert f.total_feed_kg == 4 * 50

    def test_sold_birds_and_weight(self, farm, make_flock):
        f = make_flock(farm)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=400, total_weight_kg=Decimal("800"))
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=100, total_weight_kg=Decimal("210"))
        assert f.total_sold_birds == 500
        assert f.total_sold_weight_kg == Decimal("1010")

    def test_live_birds(self, farm, make_flock):
        f = make_flock(farm, chicks=1000)
        _entry(f, 1, mortality=50)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=600, total_weight_kg=Decimal("1200"))
        assert f.live_birds == 1000 - 50 - 600

    def test_total_medication_cost(self, farm, make_flock):
        f = make_flock(farm)
        Medication.objects.create(flock=f, date=f.placement_date, name="Vit", cost=Decimal("120.50"))
        Medication.objects.create(flock=f, date=f.placement_date, name="Anti", cost=Decimal("80"))
        assert f.total_medication_cost == Decimal("200.50")

    def test_med_cost_zero_when_none(self, farm, make_flock):
        f = make_flock(farm)
        assert f.total_medication_cost == 0


class TestFlockFCR:
    def test_fcr_none_when_active(self, farm, make_flock):
        f = make_flock(farm, status="active")
        _entry(f, 1, bfp=40)  # 2000 kg
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=1, total_weight_kg=Decimal("1000"))
        assert f.fcr is None  # only computed for closed flocks

    def test_fcr_none_when_no_sales(self, farm, make_flock):
        f = make_flock(farm, status="closed")
        _entry(f, 1, bfp=40)
        assert f.fcr is None

    def test_fcr_value(self, farm, make_flock):
        f = make_flock(farm, status="closed")
        _entry(f, 1, bfp=40)  # 40 bags * 50 = 2000 kg
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=1000, total_weight_kg=Decimal("1250"))
        # 2000 / 1250 = 1.6
        assert f.fcr == 1.6


class TestFlockValidation:
    def test_age_days(self, farm, make_flock):
        f = make_flock(farm, placed_days_ago=10)
        assert f.age_days == 10


class TestPermissionsModel:
    def test_admin_can_edit_any_farm(self, farm, admin_user):
        assert admin_user.profile.can_edit_farm(farm) is True

    def test_supervisor_by_region(self, farm, supervisor_user):
        supervisor_user.profile.assigned_regions = ["Zone-A"]
        supervisor_user.profile.save()
        assert supervisor_user.profile.can_edit_farm(farm) is True

    def test_supervisor_without_assignment_can_cover(self, farm, supervisor_user):
        """Any supervisor may enter data for any farm (covering for a colleague),
        but only the farm's own region manages its details."""
        assert supervisor_user.profile.can_edit_farm(farm) is True
        supervisor_user.profile.assigned_regions = []
        supervisor_user.profile.save()
        supervisor_user.profile.assigned_farms.clear()
        assert supervisor_user.profile.can_manage_farm(farm) is False

    def test_supervisor_by_direct_assignment(self, farm, supervisor_user):
        supervisor_user.profile.assigned_farms.add(farm)
        assert supervisor_user.profile.can_edit_farm(farm) is True

    def test_is_admin_flag(self, admin_user, supervisor_user):
        assert admin_user.profile.is_admin is True
        assert supervisor_user.profile.is_admin is False
