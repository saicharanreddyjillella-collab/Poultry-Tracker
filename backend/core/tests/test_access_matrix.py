"""Role access matrix — every endpoint × role, including cross-region access.

Roles: admin; supA = supervisor of Zone-A (B is someone else's region);
plant = feed mill (feed screens only); anon = not logged in.
Expected codes come from the access policy agreed with Sai (2026-11-15):
supervisors see/edit only their regions (other regions → 404), bills for own
farms only, billing settings admin-only, plant = feed only.
"""
import datetime
from decimal import Decimal

import pytest
from django.apps import apps
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from core.billing import generate_bill
from core.models import DailyEntry, Farm, FeedOrder, Flock, Medication, Sale, UserProfile

pytestmark = pytest.mark.django_db
T = datetime.date.today()


def _client(role, name, regions=()):
    u = User.objects.create_user(name, password="pass12345")
    p = UserProfile.objects.create(user=u, role=role, assigned_regions=list(regions))
    p.sync_farms_from_regions()
    c = APIClient()
    tok = c.post("/api/auth/login/", {"username": name, "password": "pass12345"}, format="json").data["access"]
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tok}")
    return c


@pytest.fixture
def world(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    A = Farm.objects.create(farm_code="A1", name="FarmA", owner_name="a", region="Zone-A", capacity=5000)
    B = Farm.objects.create(farm_code="B1", name="FarmB", owner_name="b", region="Zone-B", capacity=5000,
                            pan="ABCPB1234B")
    fa = Flock.objects.create(farm=A, placement_date=T - datetime.timedelta(days=20), chick_count=1000)
    fb = Flock.objects.create(farm=B, placement_date=T - datetime.timedelta(days=20), chick_count=1000)
    fa2 = Flock.objects.create(farm=A, placement_date=T - datetime.timedelta(days=60), chick_count=1000, status="closed")
    fb2 = Flock.objects.create(farm=B, placement_date=T - datetime.timedelta(days=60), chick_count=1000, status="closed")
    for f in (fa, fb, fa2, fb2):
        DailyEntry.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=1), mortality_count=1)
        Sale.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=15), bird_count=10,
                            total_weight_kg=Decimal("20"), rate_per_kg=Decimal("100"))
        Medication.objects.create(flock=f, name="Vit", date=f.placement_date, cost=Decimal("100"))
    generate_bill(fa2)
    generate_bill(fb2)
    oa = FeedOrder.objects.create(farm=A, flock=fa, feed_type="BFP", quantity_bags=5)
    ob = FeedOrder.objects.create(farm=B, flock=fb, feed_type="BFP", quantity_bags=5)
    admin = _client("admin", "adm")
    doc = admin.post("/api/documents/", {"farm": B.id, "doc_type": "kyc", "file": SimpleUploadedFile(
        "k.pdf", b"%PDF", content_type="application/pdf")}, format="multipart").data["id"]
    return {
        "A": A, "B": B, "fa": fa, "fb": fb, "fa2": fa2, "fb2": fb2, "oa": oa, "ob": ob, "doc": doc,
        "eb": DailyEntry.objects.filter(flock=fb).first(), "sb": Sale.objects.filter(flock=fb).first(),
        "c": {"admin": admin, "supA": _client("supervisor", "supa", ["Zone-A"]),
              "plant": _client("plant", "plnt"), "anon": APIClient()},
    }


# url template, expected status for (admin, supA, plant, anon)
READS = [
    ("/api/farms/{B.id}/",                      (200, 404, 200, 401)),   # plant: name only
    ("/api/flocks/{fb.id}/",                    (200, 404, 403, 401)),
    ("/api/flocks/{fa.id}/",                    (200, 200, 403, 401)),
    ("/api/flocks/?status=active",              (200, 200, 403, 401)),
    ("/api/daily-entries/?flock={fb.id}",       (200, 200, 403, 401)),   # supA: empty list
    ("/api/sales/?flock={fb.id}",               (200, 200, 403, 401)),
    ("/api/medications/?flock={fb.id}",         (200, 200, 403, 401)),
    ("/api/documents/{doc}/",                   (200, 404, 404, 401)),
    ("/api/feed-orders/",                       (200, 200, 200, 401)),
    ("/api/feed-transfers/",                    (200, 200, 200, 401)),
    ("/api/feed-stock/",                        (200, 200, 200, 401)),
    ("/api/feed-rates/",                        (200, 200, 200, 401)),
    ("/api/dashboard/",                         (200, 200, 403, 401)),
    ("/api/flocks/{fb.id}/cumulative/",         (200, 404, 403, 401)),
    ("/api/flocks/{fa.id}/cumulative/",         (200, 200, 403, 401)),
    ("/api/farms/{B.id}/cumulative/",           (200, 404, 403, 401)),
    ("/api/farms/{B.id}/performance-history/",  (200, 404, 403, 401)),
    ("/api/reports/monthly/",                   (200, 200, 403, 401)),
    ("/api/reports/region/",                    (200, 200, 403, 401)),
    ("/api/reports/till-date/",                 (200, 200, 403, 401)),
    ("/api/reports/monthly/export/",            (200, 200, 403, 401)),
    ("/api/flocks/{fb.id}/export/",             (200, 404, 403, 401)),
    ("/api/flocks/{fa.id}/export/",             (200, 200, 403, 401)),
    ("/api/bill-config/",                       (200, 403, 403, 401)),
    ("/api/flocks/{fb2.id}/bill/",              (200, 404, 403, 401)),
    ("/api/flocks/{fa2.id}/bill/",              (200, 200, 403, 401)),   # own farm's bill
    ("/api/flocks/{fb2.id}/bill-history/",      (200, 404, 403, 401)),
    ("/api/bills/",                             (200, 200, 403, 401)),
    ("/api/reports/owner-dashboard/",           (200, 403, 403, 401)),
    ("/api/reports/break-even/",                (200, 403, 403, 401)),
    ("/api/reports/feed-forecast/",             (200, 403, 403, 401)),
    ("/api/audit-log/",                         (200, 403, 403, 401)),
    ("/api/trash/",                             (200, 403, 403, 401)),
    ("/api/auth/users/",                        (200, 403, 403, 401)),
    ("/api/flocks/999999/cumulative/",          (404, 404, 403, 401)),   # was a 500
    ("/api/farms/999999/cumulative/",           (404, 404, 403, 401)),   # was a 500
    ("/api/flocks/999999/export/",              (404, 404, 403, 401)),   # was a 500
]
ROLES = ("admin", "supA", "plant", "anon")


@pytest.mark.parametrize("url,expected", READS, ids=[r[0] for r in READS])
def test_read_matrix(world, url, expected):
    full = url.format(**world)
    got = tuple(world["c"][r].get(full).status_code for r in ROLES)
    assert got == expected, f"{full}: got {dict(zip(ROLES, got))}"


@pytest.mark.parametrize("url", ["/api/farms/", "/api/flocks/?status=active", "/api/feed-orders/",
                                 "/api/feed-transfers/", "/api/feed-stock/", "/api/dashboard/", "/api/bills/",
                                 "/api/reports/region/", "/api/reports/till-date/",
                                 "/api/daily-entries/?flock={fb.id}"])
def test_supervisor_lists_contain_only_their_region(world, url):
    body = world["c"]["supA"].get(url.format(**world)).content.decode()
    assert "FarmB" not in body and '"B1"' not in body and "Zone-B" not in body


def test_plant_sees_farm_names_only(world):
    rows = world["c"]["plant"].get("/api/farms/").data
    assert {r["farm_code"] for r in rows} == {"A1", "B1"}
    assert set(rows[0]) == {"id", "farm_code", "name", "region"}           # no PAN / grower data


def _write(c, method, url, body=None, multipart=False):
    if multipart:
        return c.post(url, body, format="multipart")
    return getattr(c, method)(url, body or {}, format="json")


# label, method, url, body, expected (supA, plant, anon) — admin covered by feature tests
WRITES = [
    ("entry on other region",   "post",  "/api/daily-entries/", lambda w: {"flock": w["fb"].id, "date": str(T - datetime.timedelta(days=5)), "mortality_count": 0}, (403, 403, 401)),
    ("edit other-region entry", "patch", "/api/daily-entries/{eb.id}/", lambda w: {"mortality_count": 0}, (404, 403, 401)),
    ("edit other-region sale",  "patch", "/api/sales/{sb.id}/", lambda w: {"rate_per_kg": "1"}, (404, 403, 401)),
    ("medication other region", "post",  "/api/medications/", lambda w: {"flock": w["fb"].id, "name": "x", "date": str(T), "cost": "1"}, (403, 403, 401)),
    ("edit other-region farm",  "patch", "/api/farms/{B.id}/", lambda w: {"owner_name": "x"}, (404, 403, 401)),
    ("edit other-region flock", "patch", "/api/flocks/{fb.id}/", lambda w: {"chick_count": 1}, (404, 403, 401)),
    ("flock on other region",   "post",  "/api/flocks/", lambda w: {"farm": w["B"].id, "placement_date": str(T), "chick_count": 10}, (403, 403, 401)),
    ("farm in other region",    "post",  "/api/farms/", lambda w: {"farm_code": "Z8", "name": "Z", "owner_name": "z", "capacity": 10, "region": "Zone-B"}, (400, 403, 401)),
    ("feed order other region", "post",  "/api/feed-orders/", lambda w: {"farm": w["B"].id, "feed_type": "BFP", "quantity_bags": 1}, (403, 403, 401)),
    ("edit other-region order", "patch", "/api/feed-orders/{ob.id}/", lambda w: {"quantity_bags": 999}, (404, 403, 401)),
    ("delete own order (plant)","delete","/api/feed-orders/{oa.id}/", None, (None, 403, 401)),
    ("transfer from other reg", "post",  "/api/feed-transfers/", lambda w: {"from_farm": w["B"].id, "to_farm": w["A"].id, "feed_type": "BFP", "quantity_bags": 1, "date": str(T)}, (403, 403, 401)),
    ("transfer to other region","post",  "/api/feed-transfers/", lambda w: {"from_farm": w["A"].id, "to_farm": w["B"].id, "feed_type": "BFP", "quantity_bags": 1, "date": str(T)}, (403, 403, 401)),
    ("mark other order sent",   "post",  "/api/feed-orders/{ob.id}/mark-sent/", None, (403, 200, 401)),
    ("feed rate",               "post",  "/api/feed-rates/", lambda w: {"week_start_date": str(T), "feed_type": "BFP", "rate_per_kg": "44"}, (403, 403, 401)),
    ("bill settings",           "put",   "/api/bill-config/", lambda w: {"feed_cost_per_kg": "1"}, (403, 403, 401)),
    ("close other-region flock","post",  "/api/flocks/{fb.id}/close-and-bill/", None, (404, 403, 401)),
    ("closed other flock bill", "post",  "/api/flocks/{fb2.id}/close-and-bill/", None, (404, 403, 401)),
    ("delete other-region farm","delete","/api/farms/{B.id}/", None, (404, 403, 401)),
]


@pytest.mark.parametrize("label,method,url,body,expected", WRITES, ids=[w[0] for w in WRITES])
def test_write_matrix(world, label, method, url, body, expected):
    full = url.format(**world)
    for role, exp in zip(("supA", "plant", "anon"), expected):
        if exp is None:
            continue
        r = _write(world["c"][role], method, full, body(world) if body else None)
        assert r.status_code == exp, f"{label} as {role}: {r.status_code} {getattr(r, 'data', '')}"


def test_supervisor_can_still_work_in_own_region(world):
    c, A, fa = world["c"]["supA"], world["A"], world["fa"]
    assert c.post("/api/flocks/", {"farm": A.id, "placement_date": str(T), "chick_count": 10}, format="json").status_code == 201
    assert c.post("/api/feed-orders/", {"farm": A.id, "flock": fa.id, "feed_type": "BFP", "quantity_bags": 2}, format="json").status_code == 201
    assert c.patch(f"/api/feed-orders/{world['oa'].id}/", {"quantity_bags": 6}, format="json").status_code == 200
    assert c.post("/api/farms/", {"farm_code": "A9", "name": "New A", "owner_name": "x", "capacity": 100,
                                  "region": "Zone-A"}, format="json").status_code == 201


def test_order_cannot_point_at_another_farms_flock(world):
    c = world["c"]["supA"]
    r = c.post("/api/feed-orders/", {"farm": world["A"].id, "flock": world["fa"].id, "feed_type": "BFP",
                                     "quantity_bags": 1}, format="json")
    assert r.status_code == 201        # fa is on farm A — fine
    r = c.post("/api/feed-orders/", {"farm": world["A"].id, "flock": world["fa2"].id, "feed_type": "BFP",
                                     "quantity_bags": 1}, format="json")
    assert r.status_code == 409        # fa2 is billed (E5 lock)
    r = world["c"]["admin"].post("/api/feed-orders/", {"farm": world["A"].id, "flock": world["fb"].id,
                                                       "feed_type": "BFP", "quantity_bags": 1}, format="json")
    assert r.status_code == 400        # flock from farm B on an order for farm A


def test_dispatched_order_is_locked_for_supervisor(world):
    oa = world["oa"]
    world["c"]["plant"].post(f"/api/feed-orders/{oa.id}/mark-sent/")
    r = world["c"]["supA"].patch(f"/api/feed-orders/{oa.id}/", {"quantity_bags": 50}, format="json")
    assert r.status_code == 403 and "sent" in str(r.data)


def test_supervisor_without_regions_cannot_create_farms(world):
    c = _client("supervisor", "noregion")
    r = c.post("/api/farms/", {"farm_code": "Q1", "name": "Q", "owner_name": "q", "capacity": 10, "region": "Zone-Q"},
               format="json")
    assert r.status_code == 403


@pytest.mark.skipif(not apps.is_installed("chicken_center"), reason="Feeds-only build has no other businesses")
@pytest.mark.parametrize("url", ["/api/layer/flocks/", "/api/inventory/items/", "/api/chicken/sales/",
                                 "/api/accounting/reports/pnl/", "/api/accounting/parties/"])
def test_other_businesses_are_admin_only(world, url):
    """Chicken Center / Layer Farm / their accounting & inventory: admin only."""
    assert world["c"]["admin"].get(url).status_code != 403
    for role in ("supA", "plant"):
        r = world["c"][role].get(url)
        assert r.status_code == 403, f"{role} {url} → {r.status_code}"
    assert world["c"]["anon"].get(url).status_code == 401


def test_updating_this_weeks_rate_corrects_it(world):
    admin = world["c"]["admin"]
    body = {"week_start_date": str(T), "feed_type": "BSC", "rate_per_kg": "46"}
    assert admin.post("/api/feed-rates/", body, format="json").status_code == 201
    r = admin.post("/api/feed-rates/", {**body, "rate_per_kg": "47.50"}, format="json")
    assert r.status_code == 200 and r.data["rate_per_kg"] == "47.50"
    from core.models import FeedRate
    assert FeedRate.objects.filter(week_start_date=T, feed_type="BSC").count() == 1
