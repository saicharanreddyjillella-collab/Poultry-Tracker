"""Shared pytest fixtures for the poultry-suite backend test suite."""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import UserProfile, Farm, Flock, DailyEntry, Sale, Medication, BillConfig


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def admin_user(db):
    u = User.objects.create_user(username="admin", password="pass12345")
    UserProfile.objects.create(user=u, role="admin")
    return u


@pytest.fixture
def supervisor_user(db):
    u = User.objects.create_user(username="sup", password="pass12345")
    UserProfile.objects.create(user=u, role="supervisor")
    return u


@pytest.fixture
def auth_admin(api, admin_user):
    resp = api.post("/api/auth/login/", {"username": "admin", "password": "pass12345"}, format="json")
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
    return api


@pytest.fixture
def farm(db):
    return Farm.objects.create(
        farm_code="F001", name="Test Farm", owner_name="Ramesh",
        region="Zone-A", capacity=5000,
    )


@pytest.fixture
def config(db):
    return BillConfig.get_active()


def _make_flock(farm, chicks=1000, placed_days_ago=42, status="closed"):
    placement = datetime.date.today() - datetime.timedelta(days=placed_days_ago)
    return Flock.objects.create(
        farm=farm, placement_date=placement, chick_count=chicks, status=status,
    )


@pytest.fixture
def make_flock(db):
    return _make_flock


@pytest.fixture(autouse=True)
def _clear_throttle_cache():
    """Reset DRF throttle state (stored in the cache) between tests so the
    login rate limit doesn't leak across the many auth_admin logins."""
    from django.core.cache import cache
    cache.clear()
    yield
