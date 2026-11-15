"""E5 — settled-bill immutability and the admin reopen trail."""
import datetime
from decimal import Decimal

import pytest
from django.db import transaction
from rest_framework.test import APIClient

from core.billing import generate_bill
from core.billlock import BillLocked, unlocked
from core.models import (
    AuditLog, Bill, BillVersion, DailyEntry, Farm, FeedTransfer, Flock, Sale,
)

pytestmark = pytest.mark.django_db


def blocked(fn):
    """Assert fn() raises BillLocked. Deletes raise inside Django's own
    atomic(savepoint=False); run under a savepoint so the test transaction
    survives (production runs autocommit, where this doesn't arise)."""
    with pytest.raises(BillLocked):
        with transaction.atomic():
            fn()

REASON = "Trader weighbridge slip corrected — 40 kg was missed"


def _billed_flock(farm, make_flock, user=None):
    f = make_flock(farm, chicks=1000)
    DailyEntry.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=1),
                              mortality_count=5, feed_bfp_bags=60)
    Sale.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=40),
                        bird_count=995, total_weight_kg=Decimal("2000"),
                        rate_per_kg=Decimal("100"))
    bill = generate_bill(f, user)
    return f, bill


@pytest.fixture
def billed(farm, make_flock, config, admin_user):
    return _billed_flock(farm, make_flock, admin_user)


@pytest.fixture
def auth_sup(supervisor_user, farm):
    supervisor_user.profile.assigned_farms.add(farm)
    c = APIClient()
    r = c.post("/api/auth/login/", {"username": "sup", "password": "pass12345"}, format="json")
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


class TestModelLevelLock:
    def test_first_bill_is_version_1(self, billed):
        _, bill = billed
        assert bill.version == 1

    def test_bill_cannot_be_edited(self, billed):
        _, bill = billed
        bill.net_payable = Decimal("1")
        with pytest.raises(BillLocked):
            bill.save()

    def test_bill_cannot_be_deleted(self, billed):
        _, bill = billed
        blocked(bill.delete)
        assert Bill.objects.filter(pk=bill.pk).exists()

    def test_flock_cannot_be_edited_or_deleted(self, billed):
        f, _ = billed
        f.chick_count = 2000
        with pytest.raises(BillLocked):
            f.save()
        blocked(Flock.objects.get(pk=f.pk).delete)

    def test_farm_delete_blocked_when_it_has_a_billed_flock(self, billed, farm):
        blocked(farm.delete)
        assert Farm.objects.filter(pk=farm.pk).exists()

    def test_children_locked_create_update_delete(self, billed):
        f, _ = billed
        with pytest.raises(BillLocked):
            DailyEntry.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=2),
                                      mortality_count=1)
        sale = Sale.objects.get(flock=f)
        sale.total_weight_kg = Decimal("2040")
        with pytest.raises(BillLocked):
            sale.save()
        blocked(sale.delete)

    def test_feed_transfer_touching_billed_flock_is_locked(self, billed, farm):
        f, _ = billed
        other = Farm.objects.create(farm_code="F002", name="Other", owner_name="X", capacity=1000)
        with pytest.raises(BillLocked):
            FeedTransfer.objects.create(from_farm=farm, to_farm=other, from_flock=f,
                                        feed_type="BFP", quantity_bags=2,
                                        date=datetime.date.today())

    def test_moving_a_row_off_a_billed_flock_is_locked(self, billed, farm, make_flock):
        """Re-pointing a sale away from a billed flock changes that settlement too."""
        f, _ = billed
        sale = Sale.objects.get(flock=f)
        # a second, unbilled active flock on another farm
        other_farm = Farm.objects.create(farm_code="F003", name="O", owner_name="Y", capacity=1000)
        other = make_flock(other_farm, status="active")
        sale.flock = other
        with pytest.raises(BillLocked):
            sale.save()

    def test_unbilled_flock_is_not_locked(self, farm, make_flock, config):
        f = make_flock(farm, status="active")
        e = DailyEntry.objects.create(flock=f, date=f.placement_date, mortality_count=1)
        e.mortality_count = 2
        e.save()
        e.delete()
        f.chick_count = 1200
        f.save()

    def test_unlocked_context_bypasses(self, billed):
        f, _ = billed
        with unlocked():
            DailyEntry.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=3),
                                      mortality_count=1)
        # and the lock is back afterwards
        with pytest.raises(BillLocked):
            DailyEntry.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=4))


class TestApiLock:
    def test_api_edit_returns_409(self, billed, auth_admin):
        f, _ = billed
        sale = Sale.objects.get(flock=f)
        r = auth_admin.patch(f"/api/sales/{sale.id}/", {"total_weight_kg": "2040"}, format="json")
        assert r.status_code == 409
        assert "reopen" in r.data["detail"].lower()
        sale.refresh_from_db()
        assert sale.total_weight_kg == Decimal("2000")

    def test_api_new_entry_on_billed_flock_returns_409(self, billed, auth_admin):
        f, _ = billed
        r = auth_admin.post("/api/daily-entries/", {
            "flock": f.id, "date": str(f.placement_date + datetime.timedelta(days=5)),
            "mortality_count": 1,
        }, format="json")
        assert r.status_code == 409

    def test_api_delete_flock_returns_409(self, billed, auth_admin):
        f, _ = billed
        with transaction.atomic():
            r = auth_admin.delete(f"/api/flocks/{f.id}/")
        assert r.status_code == 409
        assert Flock.objects.filter(pk=f.pk).exists()


class TestReopen:
    def url(self, f):
        return f"/api/flocks/{f.id}/reopen-bill/"

    def test_requires_admin(self, billed, auth_sup):
        f, _ = billed
        r = auth_sup.post(self.url(f), {"reason": REASON}, format="json")
        assert r.status_code == 403
        assert Bill.objects.filter(flock=f).exists()

    @pytest.mark.parametrize("reason", ["", "   ", "too short"])
    def test_requires_reason(self, billed, auth_admin, reason):
        f, _ = billed
        r = auth_admin.post(self.url(f), {"reason": reason}, format="json")
        assert r.status_code == 400
        assert Bill.objects.filter(flock=f).exists()

    def test_404_when_no_bill(self, farm, make_flock, auth_admin):
        f = make_flock(farm, status="active")
        assert auth_admin.post(self.url(f), {"reason": REASON}, format="json").status_code == 404

    def test_reopen_archives_and_unlocks(self, billed, auth_admin, admin_user):
        f, bill = billed
        old_net = bill.net_payable
        r = auth_admin.post(self.url(f), {"reason": REASON}, format="json")
        assert r.status_code == 200, r.data
        assert r.data["next_version"] == 2

        f.refresh_from_db()
        assert f.status == "active"
        assert not Bill.objects.filter(flock=f).exists()
        v = BillVersion.objects.get(flock=f)
        assert (v.version, v.reason, v.reopened_by) == (1, REASON, admin_user)
        assert v.net_payable == old_net
        assert Decimal(v.data["net_payable"]) == old_net      # full snapshot kept

        # data is now editable again
        sale = Sale.objects.get(flock=f)
        sale.total_weight_kg = Decimal("2040")
        sale.save()

    def test_rebill_after_reopen_is_version_2_and_relocks(self, billed, auth_admin):
        f, bill1 = billed
        auth_admin.post(self.url(f), {"reason": REASON}, format="json")
        sale = Sale.objects.get(flock=f)
        sale.total_weight_kg = Decimal("2040")
        sale.save()

        r = auth_admin.post(f"/api/flocks/{f.id}/close-and-bill/", {}, format="json")
        assert r.status_code == 201, r.data
        assert r.data["version"] == 2
        bill2 = Bill.objects.get(flock=f)
        assert bill2.total_sold_weight_kg == Decimal("2040")
        assert bill2.net_payable != bill1.net_payable
        # locked again
        sale.total_weight_kg = Decimal("2000")
        with pytest.raises(BillLocked):
            sale.save()

    def test_history_lists_versions(self, billed, auth_admin):
        f, _ = billed
        auth_admin.post(self.url(f), {"reason": REASON}, format="json")
        auth_admin.post(f"/api/flocks/{f.id}/close-and-bill/", {}, format="json")
        auth_admin.post(self.url(f), {"reason": REASON + " (second pass)"}, format="json")
        auth_admin.post(f"/api/flocks/{f.id}/close-and-bill/", {}, format="json")

        r = auth_admin.get(f"/api/flocks/{f.id}/bill-history/")
        assert r.status_code == 200
        assert [v["version"] for v in r.data["versions"]] == [1, 2]
        assert r.data["versions"][0]["reopened_by_username"] == "admin"
        assert r.data["current"]["version"] == 3

    def test_archived_versions_are_permanent(self, billed, auth_admin):
        f, _ = billed
        auth_admin.post(self.url(f), {"reason": REASON}, format="json")
        v = BillVersion.objects.get(flock=f)
        blocked(v.delete)
        # a reopened flock with history still can't be deleted (money trail)
        blocked(Flock.objects.get(pk=f.pk).delete)

    def test_reopen_is_audited(self, billed, auth_admin):
        f, bill = billed
        auth_admin.post(self.url(f), {"reason": REASON}, format="json")
        assert AuditLog.objects.filter(model="Bill", object_id=str(bill.pk), action="delete",
                                       actor_username="admin").exists()
        assert AuditLog.objects.filter(model="BillVersion", action="create").exists()

    def test_tds_fy_aggregate_does_not_double_count_reopened_bill(self, billed, auth_admin):
        """The archived version is not a Bill row, so the FY TDS aggregate on
        re-bill counts only the live settlement for this flock."""
        f, _ = billed
        auth_admin.post(self.url(f), {"reason": REASON}, format="json")
        assert Bill.objects.filter(flock__farm=f.farm).count() == 0
