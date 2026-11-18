"""Heat-stress forecast: heat index, bird/shed adjustments, region points, the report."""
import datetime
import io
import json

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient

from core import heat
from core.models import Farm, Flock, RegionLocation, UserProfile

pytestmark = pytest.mark.django_db
T = datetime.date.today()
D = datetime.timedelta


def client_for(username, role, regions=()):
    u = User.objects.create_user(username=username, password="pass12345")
    p = UserProfile.objects.create(user=u, role=role, assigned_regions=list(regions))
    p.sync_farms_from_regions()
    c = APIClient()
    r = c.post("/api/auth/login/", {"username": username, "password": "pass12345"}, format="json")
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


def flock(code, region, age, shed="OPEN"):
    farm = Farm.objects.create(farm_code=code, name=f"Farm {code}", owner_name="o", region=region,
                               capacity=5000, shed_type=shed)
    return Flock.objects.create(farm=farm, placement_date=T - D(days=age), chick_count=1000)


def day_at(temp, rh, n=0):
    return {"date": T + D(days=n), "hours": [(14, temp, rh), (6, temp - 8, rh + 20)]}


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def weather(monkeypatch):
    """Per-region forecast: {lat: [(temp, rh) per day]}; records calls."""
    plan = {"calls": 0, "by_lat": {}}

    def fake(lat, lon, start):
        plan["calls"] += 1
        days = plan["by_lat"].get(round(float(lat), 2))
        if days is None:
            raise heat.WeatherUnavailable("down")
        return [day_at(t, rh, n) for n, (t, rh) in enumerate(days)]
    monkeypatch.setattr(heat, "fetch_forecast", fake)
    return plan


@pytest.fixture
def world(db, weather):
    RegionLocation.objects.create(region="Zone-A", latitude="17.38500", longitude="78.48670")
    RegionLocation.objects.create(region="Zone-B", latitude="18.00000", longitude="79.00000")
    weather["by_lat"][17.39] = [(30, 50), (34, 45), (40, 40), (31, 55), (27, 60)]
    weather["by_lat"][18.0] = [(25, 50)] * 5
    return {"heavy": flock("A1", "Zone-A", 30), "chicks": flock("A2", "Zone-A", 5),
            "ec": flock("A3", "Zone-A", 20, shed="EC"), "cool": flock("B1", "Zone-B", 30),
            "admin": client_for("boss", "admin"), "supA": client_for("supa", "supervisor", ["Zone-A"]),
            "plant": client_for("mill", "plant"), "weather": weather}


# ── the heat index and adjustments ───────────────────────────────────────────

@pytest.mark.parametrize("temp,rh,level", [(26, 50, "none"), (28, 50, "watch"), (34, 45, "danger"),
                                           (40, 40, "emergency"), (33, 90, "emergency")])
def test_heat_index_bands(temp, rh, level):
    assert heat.base_level(heat.thi(temp, rh)) == level


@pytest.mark.parametrize("base,age,shed,expected", [
    ("danger", 20, "OPEN", "danger"),
    ("danger", 30, "OPEN", "emergency"),          # heavy birds suffer most
    ("none", 35, "OPEN", "none"),                 # no heat → age adds nothing
    ("danger", 5, "OPEN", "none"),                # chicks need warmth
    ("emergency", 5, "OPEN", "watch"),
    ("danger", 30, "EC", "danger"),               # controlled shed: one level down
    ("watch", 20, "EC", "none"),
])
def test_bird_age_and_shed_adjust_the_risk(base, age, shed, expected):
    assert heat.farm_level(base, age, shed) == expected


def test_peak_hour_is_the_hottest_combination():
    r = heat.daily_risk(day_at(36, 40))
    assert r["peak_hour"] == 14 and r["peak_temp"] == 36 and r["level"] == "danger"


# ── report ───────────────────────────────────────────────────────────────────

def test_admin_sees_every_farm_worst_first(world):
    r = world["admin"].get("/api/reports/heat-stress/").data
    names = [f["farm_code"] for f in r["farms"]]
    assert names[0] == "A1" and set(names) == {"A1", "A2", "A3", "B1"}
    a1 = r["farms"][0]
    assert [c["level"] for c in a1["days"]] == ["danger", "emergency", "emergency", "emergency", "danger"]
    assert r["summary"]["at_risk_next_3_days"] == 2           # A1 (heavy) and A3 (EC, still danger on day 3)
    assert r["summary"]["emergency_next_3_days"] == 1
    assert len(r["dates"]) == 5 and r["advice"]["emergency"]


def test_chicks_and_ec_shed_are_lower_risk(world):
    farms = {f["farm_code"]: f for f in world["admin"].get("/api/reports/heat-stress/").data["farms"]}
    assert farms["A2"]["worst_level"] == "watch"               # 5-day-old chicks on the hottest day
    assert farms["A3"]["worst_level"] == "danger"
    assert farms["B1"]["worst_level"] == "none"


def test_age_moves_with_the_forecast_day(world):
    young = flock("A9", "Zone-A", 26)                          # 28 days old on day 2 → heavy
    farms = {f["farm_code"]: f for f in world["admin"].get("/api/reports/heat-stress/").data["farms"]}
    cells = farms["A9"]["days"]
    assert [c["age"] for c in cells] == [26, 27, 28, 29, 30]
    assert cells[1]["level"] == "danger" and cells[2]["level"] == "emergency"


def test_supervisor_sees_only_their_regions(world):
    r = world["supA"].get("/api/reports/heat-stress/").data
    assert {f["region"] for f in r["farms"]} == {"Zone-A"}
    assert [x["region"] for x in r["regions"]] == ["Zone-A"]


def test_feed_mill_user_is_refused(world):
    assert world["plant"].get("/api/reports/heat-stress/").status_code == 403


def test_region_without_a_point_is_listed_not_guessed(world):
    flock("C1", "Zone-C", 30)
    r = world["admin"].get("/api/reports/heat-stress/").data
    assert r["summary"]["regions_missing_location"] == ["Zone-C"]
    assert "C1" not in [f["farm_code"] for f in r["farms"]]


def test_weather_outage_is_a_message_not_a_crash(world):
    world["weather"]["by_lat"].pop(18.0)
    r = world["admin"].get("/api/reports/heat-stress/")
    assert r.status_code == 200
    b = next(x for x in r.data["regions"] if x["region"] == "Zone-B")
    assert "not available" in b["error"] and "B1" not in [f["farm_code"] for f in r.data["farms"]]


def test_closed_flocks_are_ignored(world):
    world["heavy"].status = "closed"
    world["heavy"].save()
    codes = [f["farm_code"] for f in world["admin"].get("/api/reports/heat-stress/").data["farms"]]
    assert "A1" not in codes


# ── region points ────────────────────────────────────────────────────────────

def test_admin_sets_and_changes_a_region_point(world):
    flock("C1", "Zone-C", 10)
    rows = {r["region"]: r for r in world["admin"].get("/api/region-locations/").data}
    assert rows["Zone-C"]["latitude"] is None and rows["Zone-A"]["latitude"] == "17.38500"
    r = world["admin"].post("/api/region-locations/", {"region": "Zone-C", "latitude": 16.5, "longitude": "80.6"},
                            format="json")
    assert r.status_code == 200 and r.data["latitude"] == "16.50000"
    world["admin"].post("/api/region-locations/", {"region": "Zone-C", "latitude": 16.6, "longitude": 80.6},
                        format="json")
    assert float(RegionLocation.objects.get(region="Zone-C").latitude) == pytest.approx(16.6)


@pytest.mark.parametrize("body,field", [({"latitude": 95, "longitude": 78}, "latitude"),
                                        ({"latitude": "abc", "longitude": 78}, "latitude"),
                                        ({"latitude": 17, "longitude": 200}, "longitude")])
def test_bad_points_are_explained(world, body, field):
    r = world["admin"].post("/api/region-locations/", {"region": "Zone-A", **body}, format="json")
    assert r.status_code == 400 and field in r.data


def test_only_admin_manages_points(world):
    assert world["supA"].get("/api/region-locations/").status_code == 403
    r = world["supA"].post("/api/region-locations/", {"region": "Zone-A", "latitude": 1, "longitude": 1},
                           format="json")
    assert r.status_code == 403


# ── the real fetcher (network mocked) ────────────────────────────────────────

def test_open_meteo_payload_is_parsed_and_cached(monkeypatch):
    times = [f"{(T + D(days=d)).isoformat()}T{h:02d}:00" for d in range(5) for h in range(24)]
    payload = {"hourly": {"time": times, "temperature_2m": [30.0] * len(times),
                          "relative_humidity_2m": [50] * len(times)}}
    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        return io.BytesIO(json.dumps(payload).encode())
    monkeypatch.delenv("WEATHER_FAKE", raising=False)
    monkeypatch.setattr(heat.urllib.request, "urlopen", fake_urlopen)
    days = heat.fetch_forecast("17.385", "78.4867", T)
    assert len(days) == 5 and len(days[0]["hours"]) == 24 and days[0]["date"] == T
    assert "timezone=Asia%2FKolkata" in calls[0]
    heat.fetch_forecast("17.385", "78.4867", T)
    assert len(calls) == 1                                    # second call served from cache


def test_network_failure_raises_weather_unavailable(monkeypatch):
    def boom(url, timeout):
        raise OSError("no route")
    monkeypatch.delenv("WEATHER_FAKE", raising=False)
    monkeypatch.setattr(heat.urllib.request, "urlopen", boom)
    with pytest.raises(heat.WeatherUnavailable):
        heat.fetch_forecast(1, 1, T)


def test_fake_weather_for_browser_tests(monkeypatch):
    monkeypatch.setenv("WEATHER_FAKE", "1")
    days = heat.fetch_forecast(17, 78, T)
    assert [heat.daily_risk(d)["level"] for d in days] == ["watch", "danger", "emergency", "danger", "watch"]
