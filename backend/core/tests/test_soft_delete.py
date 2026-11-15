"""E14 — soft delete + Recycle Bin restore."""
import datetime
from decimal import Decimal

import pytest
from django.db import transaction
from rest_framework.test import APIClient

from core.billing import generate_bill
from core.billlock import BillLocked
from core.models import (AuditLog, DailyEntry, Document, Farm, FeedOrder, Flock, Medication, Sale)

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup(farm, make_flock):
    f = make_flock(farm, status="active", placed_days_ago=20)
    entries = [DailyEntry.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=i),
                                         mortality_count=2) for i in range(5)]
    sale = Sale.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=15),
                               bird_count=100, total_weight_kg=Decimal("200"), rate_per_kg=Decimal("100"))
    med = Medication.objects.create(flock=f, name="Vit-C", date=f.placement_date, cost=Decimal("500"))
    order = FeedOrder.objects.create(farm=farm, flock=f, feed_type="BFP", quantity_bags=10)
    return f, entries, sale, med, order


def trash(c):
    return c.get("/api/trash/").data


@pytest.fixture
def auth_sup(supervisor_user, farm):
    supervisor_user.profile.assigned_farms.add(farm)
    c = APIClient()
    tok = c.post("/api/auth/login/", {"username": "sup", "password": "pass12345"}, format="json").data["access"]
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tok}")
    return c


class TestSoftDelete:
    def test_api_delete_hides_but_keeps_the_row(self, auth_admin, setup, admin_user):
        f, entries, *_ = setup
        e = entries[0]
        assert auth_admin.delete(f"/api/daily-entries/{e.id}/").status_code == 204
        assert not DailyEntry.objects.filter(pk=e.pk).exists()          # hidden
        row = DailyEntry.all_objects.get(pk=e.pk)                        # but kept
        assert row.deleted_at and row.deleted_by == admin_user and row.deletion_batch
        assert auth_admin.get(f"/api/daily-entries/{e.id}/").status_code == 404
        assert len(auth_admin.get(f"/api/daily-entries/?flock={f.id}").data) == 4

    def test_deleted_rows_drop_out_of_flock_totals(self, auth_admin, setup):
        f, entries, *_ = setup
        assert f.total_mortality == 10
        auth_admin.delete(f"/api/daily-entries/{entries[0].id}/")
        f.refresh_from_db()
        assert Flock.objects.get(pk=f.pk).total_mortality == 8          # reverse relations exclude deleted

    def test_flock_delete_cascades_softly(self, auth_admin, setup):
        f, entries, sale, med, _ = setup
        assert auth_admin.delete(f"/api/flocks/{f.id}/").status_code == 204
        for model, pk in [(Flock, f.pk), (Sale, sale.pk), (Medication, med.pk)] + [(DailyEntry, e.pk) for e in entries]:
            assert not model.objects.filter(pk=pk).exists()
            assert model.all_objects.filter(pk=pk).exists()
        batches = {x.deletion_batch for x in DailyEntry.all_objects.filter(flock=f)} | \
                  {Flock.all_objects.get(pk=f.pk).deletion_batch}
        assert len(batches) == 1                                          # one action, one batch

    def test_farm_delete_cascades_to_flocks_orders_docs(self, auth_admin, farm, setup):
        f, entries, sale, med, order = setup
        assert auth_admin.delete(f"/api/farms/{farm.id}/").status_code == 204
        assert not Farm.objects.filter(pk=farm.pk).exists()
        assert not Flock.objects.filter(pk=f.pk).exists()
        assert not FeedOrder.objects.filter(pk=order.pk).exists()
        assert not DailyEntry.objects.filter(flock=f).exists()

    def test_queryset_delete_is_soft_too(self, setup):
        f, *_ = setup
        DailyEntry.objects.filter(flock=f).delete()
        assert DailyEntry.all_objects.filter(flock=f, deleted_at__isnull=False).count() == 5

    def test_audit_log_records_soft_delete_as_delete(self, auth_admin, setup):
        _, entries, *_ = setup
        auth_admin.delete(f"/api/daily-entries/{entries[0].id}/")
        log = AuditLog.objects.filter(model="DailyEntry", object_id=str(entries[0].pk)).first()
        assert log.action == "delete" and log.actor_username == "admin" and log.changes["_soft"] is True


class TestMoneyTrail:
    def _bill(self, f):
        f.status = "closed"
        f.save()
        return generate_bill(f)

    def test_billed_flock_cannot_be_deleted(self, auth_admin, setup):
        f, *_ = setup
        self._bill(f)
        with transaction.atomic():
            r = auth_admin.delete(f"/api/flocks/{f.id}/")
        assert r.status_code == 409 and Flock.objects.filter(pk=f.pk).exists()

    def test_farm_with_billed_flock_cannot_be_deleted(self, auth_admin, farm, setup):
        f, *_ = setup
        self._bill(f)
        with transaction.atomic():
            r = auth_admin.delete(f"/api/farms/{farm.id}/")
        assert r.status_code == 409 and "settled" in r.data["detail"]
        assert Farm.objects.filter(pk=farm.pk).exists() and Flock.objects.filter(pk=f.pk).exists()

    def test_entry_under_billed_flock_still_locked(self, setup):
        f, entries, *_ = setup
        self._bill(f)
        with pytest.raises(BillLocked):
            with transaction.atomic():
                entries[0].delete()


class TestRecycleBin:
    def test_admin_only(self, auth_sup):
        assert auth_sup.get("/api/trash/").status_code == 403

    def test_lists_one_row_per_delete_action(self, auth_admin, setup):
        f, entries, *_ = setup
        auth_admin.delete(f"/api/daily-entries/{entries[0].id}/")
        auth_admin.delete(f"/api/flocks/{f.id}/")
        rows = trash(auth_admin)
        assert len(rows) == 2
        flock_row = rows[0]                                                # newest first
        assert flock_row["kind"] == "Flock" and flock_row["deleted_by"] == "admin"
        assert flock_row["also_removed"] == {"Daily entry": 4, "Sale": 1, "Medication": 1}
        assert rows[1]["kind"] == "DailyEntry" and rows[1]["items_total"] == 1

    def test_restore_brings_back_exactly_that_action(self, auth_admin, setup):
        f, entries, sale, *_ = setup
        auth_admin.delete(f"/api/daily-entries/{entries[0].id}/")       # separate, earlier action
        auth_admin.delete(f"/api/flocks/{f.id}/")
        flock_batch = trash(auth_admin)[0]["batch"]
        r = auth_admin.post(f"/api/trash/{flock_batch}/restore/")
        assert r.status_code == 200 and r.data["restored"] == 7
        assert Flock.objects.filter(pk=f.pk).exists() and Sale.objects.filter(pk=sale.pk).exists()
        assert DailyEntry.objects.filter(flock=f).count() == 4             # earlier delete stays deleted
        restored = Flock.objects.get(pk=f.pk)
        assert restored.deleted_by is None and restored.deletion_batch is None
        assert AuditLog.objects.filter(model="Flock", object_id=str(f.pk), action="restore").exists()

    def test_restore_child_whose_parent_is_deleted_is_refused(self, auth_admin, setup):
        f, entries, *_ = setup
        auth_admin.delete(f"/api/daily-entries/{entries[0].id}/")
        entry_batch = trash(auth_admin)[0]["batch"]
        auth_admin.delete(f"/api/flocks/{f.id}/")
        r = auth_admin.post(f"/api/trash/{entry_batch}/restore/")
        assert r.status_code == 409 and "Restore that first" in r.data["error"]
        assert not DailyEntry.objects.filter(pk=entries[0].pk).exists()

    def test_recreated_entry_blocks_restore_with_clear_message(self, auth_admin, setup):
        f, entries, *_ = setup
        e = entries[0]
        auth_admin.delete(f"/api/daily-entries/{e.id}/")
        batch = trash(auth_admin)[0]["batch"]
        # same flock + date can be entered again (live-only uniqueness)
        DailyEntry.objects.create(flock=f, date=e.date, mortality_count=0)
        r = auth_admin.post(f"/api/trash/{batch}/restore/")
        assert r.status_code == 409 and "already exists" in r.data["error"]

    def test_farm_code_reusable_after_delete_and_restore_conflict(self, auth_admin, farm):
        auth_admin.delete(f"/api/farms/{farm.id}/")
        batch = trash(auth_admin)[0]["batch"]
        r = auth_admin.post("/api/farms/", {"farm_code": farm.farm_code, "name": "New", "owner_name": "Y",
                                            "capacity": 1000}, format="json")
        assert r.status_code == 201, r.data
        r = auth_admin.post(f"/api/trash/{batch}/restore/")
        assert r.status_code == 409 and farm.farm_code in r.data["error"]

    def test_duplicate_live_farm_code_still_rejected(self, auth_admin, farm):
        r = auth_admin.post("/api/farms/", {"farm_code": farm.farm_code, "name": "Dup", "owner_name": "Y",
                                            "capacity": 1000}, format="json")
        assert r.status_code == 400

    def test_restore_twice_is_409(self, auth_admin, setup):
        _, entries, *_ = setup
        auth_admin.delete(f"/api/daily-entries/{entries[0].id}/")
        batch = trash(auth_admin)[0]["batch"]
        assert auth_admin.post(f"/api/trash/{batch}/restore/").status_code == 200
        assert auth_admin.post(f"/api/trash/{batch}/restore/").status_code == 409

    def test_supervisor_cannot_restore(self, auth_admin, auth_sup, setup):
        _, entries, *_ = setup
        auth_admin.delete(f"/api/daily-entries/{entries[0].id}/")
        batch = trash(auth_admin)[0]["batch"]
        assert auth_sup.post(f"/api/trash/{batch}/restore/").status_code == 403

    def test_document_soft_delete_keeps_file(self, auth_admin, farm, tmp_path, settings):
        from django.core.files.uploadedfile import SimpleUploadedFile
        settings.MEDIA_ROOT = str(tmp_path)
        r = auth_admin.post("/api/documents/", {
            "farm": farm.id, "doc_type": "agreement",
            "file": SimpleUploadedFile("agreement.pdf", b"%PDF-1.4 x", content_type="application/pdf")},
            format="multipart")
        assert r.status_code == 201, r.data
        doc = Document.objects.get(pk=r.data["id"])
        path = doc.file.path
        assert auth_admin.delete(f"/api/documents/{doc.id}/").status_code == 204
        import os
        assert os.path.exists(path)                                       # file kept for restore
        batch = trash(auth_admin)[0]["batch"]
        assert auth_admin.post(f"/api/trash/{batch}/restore/").status_code == 200
        assert auth_admin.get(f"/api/documents/?farm={farm.id}").data[0]["id"] == doc.id


    def test_duplicate_live_daily_entry_rejected_but_deleted_one_doesnt_block(self, auth_admin, setup):
        f, entries, *_ = setup
        e = entries[1]
        body = {"flock": f.id, "date": str(e.date), "mortality_count": 0}
        r = auth_admin.post("/api/daily-entries/", body, format="json")
        assert r.status_code == 400 and "already exists" in str(r.data)
        auth_admin.delete(f"/api/daily-entries/{e.id}/")
        assert auth_admin.post("/api/daily-entries/", body, format="json").status_code == 201
