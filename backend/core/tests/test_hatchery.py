"""Chick quality by hatchery: recording on the flock, the hatchery list, the comparison report."""
import datetime

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import BillConfig, DailyEntry, Farm, Flock, Hatchery, UserProfile

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


_n = [0]


def flock(hatchery, age=20, chicks=1000, week1=0, later=0, status="active", doa=0, weight=None, region="Zone-A"):
    _n[0] += 1
    farm = Farm.objects.create(farm_code=f"H{_n[0]}", name=f"Farm {_n[0]}", owner_name="o", region=region,
                               capacity=10000)
    f = Flock.objects.create(farm=farm, placement_date=T - D(days=age), chick_count=chicks, status=status,
                             hatchery=hatchery, doa_count=doa, chick_weight_g=weight)
    if week1:
        DailyEntry.objects.create(flock=f, date=f.placement_date + D(days=3), mortality_count=week1)
    if later:
        DailyEntry.objects.create(flock=f, date=f.placement_date + D(days=10), mortality_count=later)
    return f


@pytest.fixture
def world(db):
    BillConfig.get_active()                                   # first-week limit 1.5%
    good, bad = Hatchery.objects.create(name="Sri Venkateswara"), Hatchery.objects.create(name="Balaji Chicks")
    return {"good": good, "bad": bad, "admin": client_for("boss", "admin"),
            "supA": client_for("supa", "supervisor", ["Zone-A"]), "plant": client_for("mill", "plant")}


def report(c, **q):
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    return c.get(f"/api/reports/hatcheries/{'?' + qs if qs else ''}")


def by_name(data):
    return {h["name"]: h for h in data["hatcheries"]}


# ── recording on the flock ───────────────────────────────────────────────────

def test_supervisor_records_chick_quality_when_placing_a_flock(world):
    farm = Farm.objects.create(farm_code="Z1", name="Zone farm", owner_name="o", region="Zone-A", capacity=6000)
    world["supA"]  # profile synced before the farm existed → re-sync
    UserProfile.objects.get(user__username="supa").sync_farms_from_regions()
    r = world["supA"].post("/api/flocks/", {"farm": farm.id, "placement_date": str(T), "chick_count": 5000,
                                            "hatchery": world["good"].id, "doa_count": 35, "chick_weight_g": "41.5"},
                           format="json")
    assert r.status_code == 201, r.data
    detail = world["supA"].get(f"/api/flocks/{r.data['id']}/").data
    assert detail["hatchery_name"] == "Sri Venkateswara" and detail["doa_count"] == 35
    assert detail["chick_weight_g"] == "41.5" and detail["chick_count"] == 5000      # DOA not deducted


@pytest.mark.parametrize("body,field", [({"doa_count": 1200}, "doa_count"),
                                        ({"chick_weight_g": "4.2"}, "chick_weight_g"),
                                        ({"chick_weight_g": "420"}, "chick_weight_g")])
def test_impossible_chick_numbers_are_explained(world, body, field):
    f = flock(None, age=2)
    r = world["admin"].patch(f"/api/flocks/{f.id}/", body, format="json")
    assert r.status_code == 400 and field in r.data


def test_retired_hatchery_cannot_be_picked_but_old_flocks_keep_it(world):
    old = flock(world["bad"])
    world["bad"].active = False
    world["bad"].save()
    new = flock(None, age=1)
    r = world["admin"].patch(f"/api/flocks/{new.id}/", {"hatchery": world["bad"].id}, format="json")
    assert r.status_code == 400 and "no longer used" in str(r.data["hatchery"])
    r = world["admin"].patch(f"/api/flocks/{old.id}/", {"doa_count": 3}, format="json")
    assert r.status_code == 200


# ── hatchery list ────────────────────────────────────────────────────────────

def test_everyone_but_the_mill_reads_the_list_only_admin_changes_it(world):
    assert [h["name"] for h in world["supA"].get("/api/hatcheries/").data] == ["Balaji Chicks", "Sri Venkateswara"]
    assert world["plant"].get("/api/hatcheries/").status_code == 403
    assert world["supA"].post("/api/hatcheries/", {"name": "X"}, format="json").status_code == 403
    r = world["admin"].post("/api/hatcheries/", {"name": "  Suguna  "}, format="json")
    assert r.status_code == 201 and r.data["name"] == "Suguna"
    assert world["admin"].post("/api/hatcheries/", {"name": "suguna"}, format="json").status_code == 400


def test_hatchery_with_flocks_is_retired_not_deleted(world):
    flock(world["bad"])
    r = world["admin"].delete(f"/api/hatcheries/{world['bad'].id}/")
    assert r.status_code == 400 and "Mark it as not used" in str(r.data)
    assert world["admin"].patch(f"/api/hatcheries/{world['bad'].id}/", {"active": False},
                                format="json").status_code == 200
    unused = Hatchery.objects.create(name="Unused")
    assert world["admin"].delete(f"/api/hatcheries/{unused.id}/").status_code == 204


# ── report ───────────────────────────────────────────────────────────────────

def test_report_is_admin_only(world):
    assert report(world["supA"]).status_code == 403
    assert report(world["plant"]).status_code == 403


def test_first_week_mortality_by_hatchery_worst_first(world):
    flock(world["good"], week1=8, later=30)                    # 0.8% first week
    flock(world["good"], week1=10)                             # 1.0%
    flock(world["bad"], week1=25, doa=20, weight=36)           # 2.5% → above 1.5% limit
    flock(world["bad"], week1=12, doa=10, weight=40)           # 1.2%
    data = report(world["admin"]).data
    assert [h["name"] for h in data["hatcheries"]] == ["Balaji Chicks", "Sri Venkateswara"]
    bad, good = by_name(data)["Balaji Chicks"], by_name(data)["Sri Venkateswara"]
    assert bad["week1_pct"] == 1.85 and bad["verdict_level"] == "high" and bad["over_limit_flocks"] == 1
    assert bad["doa_pct"] == 1.5 and bad["avg_chick_weight_g"] == 38.0 and bad["weighed_flocks"] == 2
    assert good["week1_pct"] == 0.9 and good["verdict_level"] == "ok"
    assert data["overall"]["week1_pct"] == 1.38 and data["first_week_limit_pct"] == 1.5


def test_later_deaths_are_not_first_week(world):
    flock(world["good"], week1=0, later=50)
    assert by_name(report(world["admin"]).data)["Sri Venkateswara"]["week1_pct"] == 0.0


def test_worse_than_average_but_within_limit_is_a_warning(world):
    for _ in range(3):
        flock(world["good"], week1=2)                          # 0.2%
    flock(world["bad"], week1=12)                              # 1.2%: under the limit, well above average
    assert by_name(report(world["admin"]).data)["Balaji Chicks"]["verdict_level"] == "medium"


def test_flocks_still_in_first_week_are_not_judged(world):
    flock(world["bad"], age=4, week1=40)
    bad = by_name(report(world["admin"]).data)["Balaji Chicks"]
    assert bad["week1_pct"] is None and bad["week1_flocks"] == 0 and bad["verdict_level"] is None
    assert bad["flocks"][0]["week1_mortality"] is None


def test_deleted_entries_do_not_count(world):
    f = flock(world["bad"], week1=30)
    f.daily_entries.first().delete()                           # soft delete (Recycle Bin)
    assert by_name(report(world["admin"]).data)["Balaji Chicks"]["week1_pct"] == 0.0


def test_unrecorded_hatchery_is_its_own_group_last(world):
    flock(None, week1=50)
    flock(world["good"], week1=1)
    names = [h["name"] for h in report(world["admin"]).data["hatcheries"]]
    assert names[-1] == "Not recorded"


def test_period_filter_and_final_mortality(world):
    flock(world["good"], age=300, week1=5)
    flock(world["good"], age=50, week1=5, later=45, status="closed")
    data = report(world["admin"], days=180).data
    good = by_name(data)["Sri Venkateswara"]
    assert good["flocks_count"] == 1 and good["final_mortality_pct"] == 5.0
    assert by_name(report(world["admin"], days=365).data)["Sri Venkateswara"]["flocks_count"] == 2
