"""E13 — opt-in pagination, guarded high-volume lists, global throttles."""
import datetime

import pytest
from django.core.cache import cache
from rest_framework.settings import api_settings
from rest_framework.test import APIClient

from core.models import DailyEntry, Farm, Flock, Sale

pytestmark = pytest.mark.django_db


@pytest.fixture
def data(farm, make_flock):
    f1 = make_flock(farm, status="active", placed_days_ago=30)
    farm2 = Farm.objects.create(farm_code="F002", name="Two", owner_name="X", capacity=5000)
    f2 = make_flock(farm2, status="active", placed_days_ago=20)
    for i in range(12):
        DailyEntry.objects.create(flock=f1, date=f1.placement_date + datetime.timedelta(days=i), mortality_count=1)
    for i in range(3):
        DailyEntry.objects.create(flock=f2, date=f2.placement_date + datetime.timedelta(days=i))
    return f1, f2


class TestOptionalPagination:
    def test_existing_screens_still_get_plain_lists(self, auth_admin, data):
        f1, _ = data
        for url in ("/api/farms/", "/api/bills/", f"/api/daily-entries/?flock={f1.id}",
                    f"/api/sales/?flock={f1.id}", f"/api/medications/?flock={f1.id}",
                    "/api/feed-orders/", "/api/feed-transfers/", "/api/feed-rates/"):
            r = auth_admin.get(url)
            assert r.status_code == 200, url
            assert isinstance(r.data, list), f"{url} changed shape"
        assert len(auth_admin.get(f"/api/daily-entries/?flock={f1.id}").data) == 12

    def test_page_params_return_a_page(self, auth_admin, data):
        f1, _ = data
        r = auth_admin.get(f"/api/daily-entries/?flock={f1.id}&page=2&page_size=5")
        assert r.status_code == 200
        assert r.data["count"] == 12 and len(r.data["results"]) == 5
        assert r.data["next"] and r.data["previous"]
        last = auth_admin.get(f"/api/daily-entries/?flock={f1.id}&page=3&page_size=5").data
        assert len(last["results"]) == 2 and last["next"] is None

    def test_pages_cover_every_row_exactly_once(self, auth_admin, data):
        f1, _ = data
        ids = []
        for page in (1, 2, 3):
            ids += [e["id"] for e in auth_admin.get(
                f"/api/daily-entries/?flock={f1.id}&page={page}&page_size=5").data["results"]]
        assert len(ids) == len(set(ids)) == 12

    def test_page_size_is_capped(self, auth_admin, data):
        r = auth_admin.get("/api/farms/?page_size=100000")
        assert r.status_code == 200 and "results" in r.data
        from core.pagination import OptionalPageNumberPagination
        assert OptionalPageNumberPagination.max_page_size == 500

    def test_out_of_range_page_is_404(self, auth_admin, data):
        assert auth_admin.get("/api/farms/?page=99").status_code == 404

    def test_unordered_models_page_deterministically(self, auth_admin, data):
        # Farm has no Meta.ordering — pagination must still be stable (ordered by pk)
        a = auth_admin.get("/api/farms/?page=1&page_size=1").data["results"][0]["id"]
        b = auth_admin.get("/api/farms/?page=2&page_size=1").data["results"][0]["id"]
        assert a < b


class TestGuardedLists:
    @pytest.mark.parametrize("url", ["/api/daily-entries/", "/api/sales/", "/api/medications/", "/api/flocks/"])
    def test_unfiltered_high_volume_lists_are_always_paged(self, auth_admin, data, url):
        r = auth_admin.get(url)
        assert r.status_code == 200
        assert set(r.data) >= {"count", "results"}, f"{url} returned an unbounded list"
        assert len(r.data["results"]) <= 50

    def test_unfiltered_daily_entries_paged_across_all_flocks(self, auth_admin, data):
        r = auth_admin.get("/api/daily-entries/")
        assert r.data["count"] == 15

    def test_flock_filters(self, auth_admin, data, farm):
        f1, f2 = data
        r = auth_admin.get(f"/api/flocks/?farm={farm.id}")
        assert [x["id"] for x in r.data] == [f1.id]
        assert {x["id"] for x in auth_admin.get("/api/flocks/?status=active").data} == {f1.id, f2.id}

    def test_flock_detail_unaffected(self, auth_admin, data):
        f1, _ = data
        r = auth_admin.get(f"/api/flocks/{f1.id}/")
        assert r.status_code == 200 and r.data["id"] == f1.id


class TestThrottles:
    def test_global_rates_configured(self):
        classes = api_settings.DEFAULT_THROTTLE_CLASSES
        names = {c.__name__ for c in classes}
        assert {"ScopedRateThrottle", "UserRateThrottle", "AnonRateThrottle"} <= names
        rates = api_settings.DEFAULT_THROTTLE_RATES
        assert rates["user"] == "600/min" and rates["anon"] == "60/min"

    def test_authenticated_user_is_throttled_past_the_limit(self, auth_admin, data, monkeypatch):
        from rest_framework.throttling import UserRateThrottle
        monkeypatch.setattr(UserRateThrottle, "THROTTLE_RATES", {**UserRateThrottle.THROTTLE_RATES, "user": "5/min"})
        cache.clear()
        codes = [auth_admin.get("/api/farms/").status_code for _ in range(7)]
        assert codes[:5] == [200] * 5 and codes[-1] == 429

    def test_throttles_are_per_user(self, auth_admin, data, supervisor_user, monkeypatch):
        from rest_framework.throttling import UserRateThrottle
        monkeypatch.setattr(UserRateThrottle, "THROTTLE_RATES", {**UserRateThrottle.THROTTLE_RATES, "user": "3/min"})
        cache.clear()
        for _ in range(4):
            auth_admin.get("/api/farms/")
        sup = APIClient()
        tok = sup.post("/api/auth/login/", {"username": "sup", "password": "pass12345"}, format="json").data["access"]
        sup.credentials(HTTP_AUTHORIZATION=f"Bearer {tok}")
        assert sup.get("/api/farms/").status_code == 200       # admin's burst doesn't block others

    def test_anonymous_is_throttled(self, monkeypatch):
        from rest_framework.throttling import AnonRateThrottle
        monkeypatch.setattr(AnonRateThrottle, "THROTTLE_RATES", {**AnonRateThrottle.THROTTLE_RATES, "anon": "3/min"})
        cache.clear()
        c = APIClient()
        codes = [c.get("/api/auth/check-setup/").status_code for _ in range(5)]
        assert codes[-1] == 429

    def test_health_check_is_never_throttled(self, monkeypatch):
        from rest_framework.throttling import AnonRateThrottle
        monkeypatch.setattr(AnonRateThrottle, "THROTTLE_RATES", {**AnonRateThrottle.THROTTLE_RATES, "anon": "1/min"})
        cache.clear()
        c = APIClient()
        assert all(c.get("/api/health/").status_code == 200 for _ in range(5))
