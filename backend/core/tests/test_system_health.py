"""System Health page: backups, errors, missing entries, weather, features, user activity."""
import datetime
import json
import logging

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from core import heat
from core.error_log import KEEP
from core.models import DailyEntry, ErrorEvent, Farm, FeatureSetting, Flock, RegionLocation, UserProfile

pytestmark = pytest.mark.django_db
T = datetime.date.today()
D = datetime.timedelta


def client_for(username, role, password="pass12345"):
    u = User.objects.create_user(username=username, password=password, first_name=username.title())
    UserProfile.objects.create(user=u, role=role, assigned_regions=["Zone-A"])
    c = APIClient()
    r = c.post("/api/auth/login/", {"username": username, "password": password}, format="json")
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


def health(c):
    r = c.get("/api/settings/health/")
    assert r.status_code == 200, r.data
    return r.data


def check(data, key):
    return next(c for c in data["checks"] if c["key"] == key)


@pytest.fixture
def admin(db):
    return client_for("boss", "admin")


def write_status(tmp_path, settings, hours_ago, status="ok", message="backup complete"):
    when = (timezone.now() - D(hours=hours_ago)).astimezone().isoformat(timespec="seconds")
    f = tmp_path / "last_backup.json"
    f.write_text(json.dumps({"timestamp": when, "status": status, "message": message, "db_file": "db.sql.gz",
                             "db_bytes": 5 * 1024 * 1024, "media_file": "", "offsite": "s3"}))
    settings.BACKUP_STATUS_FILE = str(f)


def test_admin_only(admin):
    sup = client_for("sup", "supervisor")
    assert sup.get("/api/settings/health/").status_code == 403
    assert health(admin)["counts"]["users"] == 2


# ── backups ──────────────────────────────────────────────────────────────────

def test_backups_not_set_up_here(admin, settings):
    settings.BACKUP_STATUS_FILE = ""
    assert check(health(admin), "backup")["status"] == "info"


@pytest.mark.parametrize("hours,status,expected,text", [
    (5, "ok", "ok", "5 h ago"),
    (30, "ok", "warn", "30 hours ago"),
    (80, "ok", "error", "3.3 days ago"),
    (2, "failed", "error", "FAILED"),
])
def test_backup_age_and_result(admin, settings, tmp_path, hours, status, expected, text):
    write_status(tmp_path, settings, hours, status, "pg_dump failed" if status == "failed" else "backup complete")
    c = check(health(admin), "backup")
    assert c["status"] == expected and text in c["detail"]


def test_missing_backup_file_is_an_error(admin, settings, tmp_path):
    settings.BACKUP_STATUS_FILE = str(tmp_path / "nope.json")
    assert check(health(admin), "backup")["detail"].startswith("No backup has run yet")


def test_overall_is_the_worst_check(admin, settings, tmp_path):
    write_status(tmp_path, settings, 80)
    assert health(admin)["overall"] == "error"


# ── errors ───────────────────────────────────────────────────────────────────

def test_logged_errors_are_kept_and_counted(admin):
    assert check(health(admin), "errors")["status"] == "ok"
    logging.getLogger("core.something").error("Bill engine blew up on flock %s", 7)
    admin.post("/api/client-errors/", {"message": "TypeError: x is undefined", "path": "/flocks/3"}, format="json")
    data = health(admin)
    assert check(data, "errors")["detail"].startswith("1 on the server, 1 on screens")
    msgs = [(e["source"], e["message"]) for e in data["recent_errors"]]
    assert ("server", "Bill engine blew up on flock 7") in msgs
    assert any(src == "screen" and "x is undefined" in m for src, m in msgs)


def test_warnings_are_not_kept_and_only_the_newest_are(admin):
    logging.getLogger("core.x").warning("just a warning")
    assert ErrorEvent.objects.count() == 0
    ErrorEvent.objects.bulk_create([ErrorEvent(level="ERROR", message=f"old {i}") for i in range(KEEP + 60)])
    logging.getLogger("core.x").error("newest")
    assert ErrorEvent.objects.count() <= KEEP + 1
    assert ErrorEvent.objects.filter(message="newest").exists()


def test_a_crash_in_a_request_is_recorded(admin, monkeypatch):
    from core.views import settings as sv
    def boom():
        raise RuntimeError("disk on fire")
    monkeypatch.setattr("core.system_health.health_report", boom)
    admin.raise_request_exception = False
    assert admin.get("/api/settings/health/").status_code == 500
    monkeypatch.undo()
    assert any("disk on fire" in e["message"] or "/api/settings/health/" in e["path"]
               for e in health(admin)["recent_errors"])


# ── entries, weather, features ───────────────────────────────────────────────

def test_flocks_missing_yesterdays_entry(admin):
    farm = Farm.objects.create(farm_code="A1", name="Lakshmi", owner_name="o", region="Zone-A", capacity=5000)
    fl = Flock.objects.create(farm=farm, placement_date=T - D(days=10), chick_count=1000)
    Flock.objects.create(farm=farm, placement_date=T, chick_count=1000)              # placed today: not due
    c = check(health(admin), "entries")
    assert c["status"] == "warn" and "Missing for 1: Lakshmi" in c["detail"]
    DailyEntry.objects.create(flock=fl, date=T - D(days=1))
    assert check(health(admin), "entries")["status"] == "ok"


def test_weather_check(admin, monkeypatch):
    assert check(health(admin), "weather")["status"] == "info"
    RegionLocation.objects.create(region="Zone-A", latitude=17.4, longitude=78.5)
    monkeypatch.setattr(heat, "fetch_forecast", lambda *a: [])
    assert check(health(admin), "weather")["status"] == "ok"
    def down(*a):
        raise heat.WeatherUnavailable("x")
    monkeypatch.setattr(heat, "fetch_forecast", down)
    assert check(health(admin), "weather")["status"] == "warn"


def test_features_listed(admin):
    FeatureSetting.objects.create(key="lift_planner", enabled=False)
    d = check(health(admin), "features")["detail"]
    assert "Off: Best Day to Lift" in d and "Feed Audit" in d


# ── who is active ────────────────────────────────────────────────────────────

def test_sign_in_and_changes_show_per_user(admin):
    sup = client_for("ravi", "supervisor")
    farm = Farm.objects.create(farm_code="A1", name="Lakshmi", owner_name="o", region="Zone-A", capacity=5000)
    UserProfile.objects.get(user__username="ravi").sync_farms_from_regions()
    r = sup.post("/api/flocks/", {"farm": farm.id, "placement_date": str(T), "chick_count": 5000}, format="json")
    assert r.status_code == 201, r.data
    users = {u["username"]: u for u in health(admin)["users"]}
    assert users["ravi"]["last_login"] is not None and users["ravi"]["changes_7d"] >= 1
    assert users["ravi"]["last_change"] is not None and users["ravi"]["role"] == "supervisor"
