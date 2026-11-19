"""Company costs and grower PAN are admin-only; supervisors keep their own entries and the grower's payment."""
import datetime
import io
import json
from decimal import Decimal

import openpyxl
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.billing import generate_bill
from core.models import DailyEntry, Farm, FeedOrder, FeedRate, Flock, Medication, Sale, UserProfile
from core.redaction import HIDDEN_FIELDS

pytestmark = pytest.mark.django_db
T = datetime.date.today()
D = datetime.timedelta


def client_for(username, role, regions=("Zone-A",)):
    u = User.objects.create_user(username=username, password="pass12345")
    p = UserProfile.objects.create(user=u, role=role, assigned_regions=list(regions))
    p.sync_farms_from_regions()
    c = APIClient()
    r = c.post("/api/auth/login/", {"username": username, "password": "pass12345"}, format="json")
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


def all_keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from all_keys(v)
    elif isinstance(o, list):
        for x in o:
            yield from all_keys(x)


@pytest.fixture
def world(db):
    FeedRate.objects.create(week_start_date=T - D(days=T.weekday()), feed_type="BFP", rate_per_kg=Decimal("44"))
    farm = Farm.objects.create(farm_code="A1", name="Lakshmi", owner_name="Ramesh", region="Zone-A", capacity=5000,
                               pan="ABCPR1234A")
    active = Flock.objects.create(farm=farm, placement_date=T - D(days=20), chick_count=5000)
    FeedOrder.objects.create(farm=farm, flock=active, feed_type="BFP", quantity_bags=50, status="delivered")
    DailyEntry.objects.create(flock=active, date=active.placement_date + D(days=1), mortality_count=3,
                              feed_bfp_bags=Decimal("5"))
    Medication.objects.create(flock=active, name="Vit C", date=T, cost=Decimal("800"))
    Sale.objects.create(flock=active, date=T, bird_count=10, total_weight_kg=Decimal("22"),
                        rate_per_kg=Decimal("101"), trader_name="t")
    farm2 = Farm.objects.create(farm_code="A2", name="Ganga", owner_name="Suresh", region="Zone-A", capacity=4000)
    closed = Flock.objects.create(farm=farm2, placement_date=T - D(days=60), chick_count=4000)
    FeedOrder.objects.create(farm=farm2, flock=closed, feed_type="BFP", quantity_bags=100, status="delivered")
    DailyEntry.objects.create(flock=closed, date=closed.placement_date + D(days=2), mortality_count=40,
                              feed_bfp_bags=Decimal("90"))
    Sale.objects.create(flock=closed, date=T - D(days=3), bird_count=3960, total_weight_kg=Decimal("8000"),
                        rate_per_kg=Decimal("100"), trader_name="t")
    closed.status = "closed"
    closed.save()
    boss = client_for("boss", "admin")
    generate_bill(closed, User.objects.get(username="boss"))
    return {"farm": farm, "active": active, "closed": closed, "admin": boss,
            "sup": client_for("sup", "supervisor"), "mill": client_for("mill", "plant", ())}


def pages(w):
    a, c, f = w["active"].id, w["closed"].id, w["farm"].id
    return ["/api/dashboard/", "/api/farms/", f"/api/farms/{f}/", "/api/flocks/", f"/api/flocks/{a}/",
            f"/api/flocks/{c}/", f"/api/flocks/{c}/bill/", f"/api/flocks/{c}/bill-history/", "/api/bills/",
            f"/api/flocks/{c}/cumulative/", f"/api/farms/{f}/cumulative/", f"/api/farms/{f}/performance-history/",
            f"/api/reports/monthly/?year={T.year}&month={T.month}", "/api/reports/region/", "/api/reports/till-date/"]


def test_supervisor_sees_no_company_cost_anywhere(world):
    for url in pages(world):
        r = world["sup"].get(url)
        assert r.status_code == 200, (url, r.status_code)
        leaked = set(all_keys(r.data)) & HIDDEN_FIELDS
        assert not leaked, (url, leaked)


def test_admin_still_sees_everything(world):
    bill = world["admin"].get(f"/api/flocks/{world['closed'].id}/bill/").data
    for k in ("chick_cost", "feed_cost", "production_cost_total", "production_cost_per_kg", "config_snapshot",
              "avg_selling_price"):
        assert k in bill, k
    assert world["admin"].get(f"/api/farms/{world['farm'].id}/").data["pan"] == "ABCPR1234A"
    till = world["admin"].get("/api/reports/till-date/").data
    assert "total_sale_amount" in till and "feed_rates" in till


def test_supervisor_keeps_the_growers_payment_and_own_entries(world):
    bill = world["sup"].get(f"/api/flocks/{world['closed'].id}/bill/").data
    for k in ("growing_charges_total", "gross_payable", "net_payable", "tds_amount", "fcr", "chicks_placed"):
        assert k in bill, k
    sale = world["sup"].get("/api/sales/").data
    rows = sale["results"] if isinstance(sale, dict) else sale
    assert rows[0]["rate_per_kg"] and rows[0]["total_amount"]
    meds = world["sup"].get(f"/api/flocks/{world['active'].id}/").data["medications"]
    assert meds[0]["cost"] == "800.00"
    farm = world["sup"].get(f"/api/farms/{world['farm'].id}/").data
    assert farm["has_valid_pan"] is True and "pan" not in farm


def test_feed_prices_are_admin_and_feed_mill_only(world):
    r = world["sup"].get("/api/feed-rates/")
    assert r.status_code == 403 and "admin only" in str(r.data["detail"])
    assert world["mill"].get("/api/feed-rates/").status_code == 200
    assert world["admin"].get("/api/feed-rates/").status_code == 200


def test_supervisor_saving_a_farm_cannot_change_or_clear_the_pan(world):
    f = world["farm"]
    r = world["sup"].patch(f"/api/farms/{f.id}/", {"pan": "", "location": "near the tank"}, format="json")
    assert r.status_code == 200, r.data
    r = world["sup"].put(f"/api/farms/{f.id}/", {"farm_code": "A1", "name": "Lakshmi", "owner_name": "Ramesh",
                                                 "region": "Zone-A", "capacity": 5000, "pan": "ZZZZZ9999Z"},
                         format="json")
    assert r.status_code == 200, r.data
    f.refresh_from_db()
    assert f.pan == "ABCPR1234A" and f.location == "near the tank"
    assert world["admin"].patch(f"/api/farms/{f.id}/", {"pan": "PQRST5678U"}, format="json").status_code == 200
    f.refresh_from_db()
    assert f.pan == "PQRST5678U"


def test_monthly_excel_has_no_cost_column_for_supervisors(world):
    def headers(c):
        r = c.get(f"/api/reports/monthly/export/?year={T.year}&month={T.month}")
        assert r.status_code == 200
        body = b"".join(r.streaming_content) if getattr(r, "streaming", False) else r.content
        return [c.value for c in openpyxl.load_workbook(io.BytesIO(body)).active[1]]
    assert "Cost/Kg" not in headers(world["sup"])
    assert headers(world["admin"])[-1] == "Cost/Kg"


def test_errors_and_signed_out_responses_are_untouched(world):
    r = APIClient().get("/api/farms/")
    assert r.status_code == 401 and "detail" in r.data
