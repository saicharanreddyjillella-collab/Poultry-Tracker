"""Settings → Features: admin switches Feed Audit / Best Day to Lift on and off."""
import datetime

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import AuditLog, Farm, FeatureSetting, FeedStockCount, Flock, MarketRate, UserProfile

pytestmark = pytest.mark.django_db
T = datetime.date.today()


def client_for(username, role, regions=()):
    u = User.objects.create_user(username=username, password="pass12345", first_name=username.title())
    p = UserProfile.objects.create(user=u, role=role, assigned_regions=list(regions))
    p.sync_farms_from_regions()
    c = APIClient()
    r = c.post("/api/auth/login/", {"username": username, "password": "pass12345"}, format="json")
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


@pytest.fixture
def world(db):
    farm = Farm.objects.create(farm_code="A1", name="A1", owner_name="o", region="Zone-A", capacity=5000)
    flock = Flock.objects.create(farm=farm, placement_date=T - datetime.timedelta(days=30), chick_count=4000)
    return {"flock": flock, "admin": client_for("boss", "admin"),
            "sup": client_for("sup", "supervisor", ["Zone-A"]), "mill": client_for("mill", "plant")}


def switch(world, key, on):
    return world["admin"].patch(f"/api/settings/features/{key}/", {"enabled": on}, format="json")


def test_features_are_on_by_default_and_everyone_can_read_the_switches(world):
    for who in ("admin", "sup", "mill"):
        assert world[who].get("/api/features/").data == {"feed_audit": True, "lift_planner": True}


def test_admin_sees_each_feature_with_what_turning_it_off_does(world):
    rows = world["admin"].get("/api/settings/features/").data
    assert [r["key"] for r in rows] == ["feed_audit", "lift_planner"]
    assert all(r["name"] and r["description"] and r["when_off"] and r["enabled"] for r in rows)
    assert rows[0]["updated_by"] is None


def test_only_admin_can_see_or_change_settings(world):
    assert world["sup"].get("/api/settings/features/").status_code == 403
    assert world["sup"].patch("/api/settings/features/feed_audit/", {"enabled": False},
                              format="json").status_code == 403
    assert world["mill"].patch("/api/settings/features/feed_audit/", {"enabled": False},
                               format="json").status_code == 403


def test_bad_requests_are_explained(world):
    assert world["admin"].patch("/api/settings/features/nope/", {"enabled": False}, format="json").status_code == 404
    r = world["admin"].patch("/api/settings/features/feed_audit/", {"enabled": "off"}, format="json")
    assert r.status_code == 400 and "enabled" in r.data


def test_turning_feed_audit_off_blocks_counts_and_report_and_keeps_data(world):
    fl = world["flock"]
    FeedStockCount.objects.create(flock=fl, date=T, bfp_bags=5)
    r = switch(world, "feed_audit", False)
    assert r.status_code == 200 and r.data["enabled"] is False and r.data["updated_by"] == "Boss"
    assert world["sup"].get("/api/features/").data["feed_audit"] is False
    r = world["sup"].post("/api/feed-counts/", {"flock": fl.id, "date": str(T), "bfp_bags": 1}, format="json")
    assert r.status_code == 403 and "turned off" in str(r.data["detail"])
    assert world["sup"].get(f"/api/feed-counts/?flock={fl.id}").status_code == 403
    assert world["admin"].get("/api/reports/feed-audit/").status_code == 403
    assert world["admin"].get("/api/reports/lift-planner/").status_code == 200        # other feature unaffected
    assert FeedStockCount.objects.count() == 1                                       # data kept
    switch(world, "feed_audit", True)
    assert len(world["sup"].get(f"/api/feed-counts/?flock={fl.id}").data) == 1


def test_turning_lift_planner_off_blocks_planner_and_rates(world):
    MarketRate.objects.create(date=T, rate_per_kg=100)
    switch(world, "lift_planner", False)
    assert world["admin"].get("/api/reports/lift-planner/").status_code == 403
    r = world["admin"].post("/api/market-rates/", {"date": str(T), "rate_per_kg": "101"}, format="json")
    assert r.status_code == 403
    assert MarketRate.objects.get().rate_per_kg == 100
    assert world["admin"].get("/api/reports/feed-audit/").status_code == 200
    switch(world, "lift_planner", True)
    assert world["admin"].get("/api/reports/lift-planner/").status_code == 200


def test_switching_is_recorded_in_the_audit_log(world):
    switch(world, "lift_planner", False)
    switch(world, "lift_planner", True)
    assert FeatureSetting.objects.get(key="lift_planner").enabled is True
    assert AuditLog.objects.filter(model="FeatureSetting").count() >= 2
