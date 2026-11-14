"""Document repository (A3): upload/list/delete attached to farm or flock."""
import datetime
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from core.models import Document, Farm

pytestmark = pytest.mark.django_db


def _file(name="agreement.pdf", content=b"%PDF-1.4 test"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class TestDocumentUpload:
    def test_upload_to_farm(self, auth_admin, farm):
        resp = auth_admin.post("/api/documents/", {
            "farm": farm.id, "doc_type": "agreement", "title": "2026 agreement",
            "file": _file(),
        }, format="multipart")
        assert resp.status_code in (200, 201), resp.data
        assert Document.objects.filter(farm=farm).count() == 1
        d = Document.objects.get(farm=farm)
        assert d.original_name == "agreement.pdf"
        assert d.uploaded_by is not None

    def test_upload_to_flock(self, auth_admin, farm, make_flock):
        f = make_flock(farm, status="active")
        resp = auth_admin.post("/api/documents/", {
            "flock": f.id, "doc_type": "vet_certificate", "file": _file("vet.pdf"),
        }, format="multipart")
        assert resp.status_code in (200, 201), resp.data
        assert Document.objects.filter(flock=f).count() == 1

    def test_upload_requires_farm_or_flock(self, auth_admin):
        resp = auth_admin.post("/api/documents/", {
            "doc_type": "other", "file": _file(),
        }, format="multipart")
        assert resp.status_code == 400

    def test_file_url_in_response(self, auth_admin, farm):
        resp = auth_admin.post("/api/documents/", {
            "farm": farm.id, "doc_type": "kyc", "file": _file("id.pdf"),
        }, format="multipart")
        assert resp.data["file_url"]
        assert resp.data["doc_type_display"] == "KYC / ID Proof"


class TestDocumentList:
    def test_list_filtered_by_farm(self, auth_admin, farm, make_flock):
        f = make_flock(farm, status="active")
        Document.objects.create(farm=farm, doc_type="agreement", file=_file())
        Document.objects.create(flock=f, doc_type="vet_certificate", file=_file("v.pdf"))
        resp = auth_admin.get(f"/api/documents/?farm={farm.id}")
        assert resp.status_code == 200
        assert len(resp.data) == 1
        resp2 = auth_admin.get(f"/api/documents/?flock={f.id}")
        assert len(resp2.data) == 1


class TestDocumentPermissions:
    def _login(self, api, username):
        r = api.post("/api/auth/login/", {"username": username, "password": "pass12345"}, format="json")
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return api

    def test_supervisor_cannot_upload_to_unassigned_farm(self, api, supervisor_user, farm):
        self._login(api, "sup")
        resp = api.post("/api/documents/", {
            "farm": farm.id, "doc_type": "agreement", "file": _file(),
        }, format="multipart")
        assert resp.status_code in (403, 400)
        assert Document.objects.filter(farm=farm).count() == 0

    def test_supervisor_can_upload_to_assigned_farm(self, api, supervisor_user, farm):
        supervisor_user.profile.assigned_regions = ["Zone-A"]
        supervisor_user.profile.save()
        self._login(api, "sup")
        resp = api.post("/api/documents/", {
            "farm": farm.id, "doc_type": "agreement", "file": _file(),
        }, format="multipart")
        assert resp.status_code in (200, 201), resp.data

    def test_delete_document(self, auth_admin, farm):
        d = Document.objects.create(farm=farm, doc_type="other", file=_file())
        resp = auth_admin.delete(f"/api/documents/{d.id}/")
        assert resp.status_code in (200, 204)
        assert Document.objects.filter(id=d.id).count() == 0


class TestDocumentModel:
    def test_owning_farm_via_flock(self, farm, make_flock):
        f = make_flock(farm, status="active")
        d = Document.objects.create(flock=f, doc_type="vet_certificate", file=_file())
        assert d.owning_farm == farm

    def test_owning_farm_direct(self, farm):
        d = Document.objects.create(farm=farm, doc_type="agreement", file=_file())
        assert d.owning_farm == farm
