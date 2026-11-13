"""API + auth + permission tests through the DRF endpoints."""
from decimal import Decimal

import pytest

from core.models import Farm, UserProfile
from django.contrib.auth.models import User

pytestmark = pytest.mark.django_db


class TestSetupAndAuth:
    def test_check_setup_true_when_no_users(self, api):
        resp = api.get("/api/auth/check-setup/")
        assert resp.status_code == 200
        assert resp.data["needs_setup"] is True

    def test_initial_setup_creates_admin(self, api):
        resp = api.post("/api/auth/setup/",
                        {"username": "boss", "password": "pass12345"}, format="json")
        assert resp.status_code in (200, 201)
        u = User.objects.get(username="boss")
        assert u.profile.role == "admin"

    def test_setup_blocked_once_a_user_exists(self, api, admin_user):
        resp = api.post("/api/auth/setup/",
                        {"username": "boss2", "password": "pass12345"}, format="json")
        assert resp.status_code >= 400
        resp2 = api.get("/api/auth/check-setup/")
        assert resp2.data["needs_setup"] is False

    def test_login_returns_jwt(self, api, admin_user):
        resp = api.post("/api/auth/login/",
                        {"username": "admin", "password": "pass12345"}, format="json")
        assert resp.status_code == 200
        assert "access" in resp.data

    def test_login_wrong_password(self, api, admin_user):
        resp = api.post("/api/auth/login/",
                        {"username": "admin", "password": "nope"}, format="json")
        assert resp.status_code >= 400


class TestAuthRequired:
    def test_farms_list_requires_auth(self, api):
        resp = api.get("/api/farms/")
        assert resp.status_code in (401, 403)

    def test_farms_list_ok_when_authed(self, auth_admin):
        resp = auth_admin.get("/api/farms/")
        assert resp.status_code == 200


class TestFarmPermissions:
    def _login(self, api, username):
        resp = api.post("/api/auth/login/",
                        {"username": username, "password": "pass12345"}, format="json")
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")
        return api

    def test_admin_can_create_farm(self, api, admin_user):
        self._login(api, "admin")
        resp = api.post("/api/farms/", {
            "farm_code": "F100", "name": "New", "owner_name": "O",
            "region": "Zone-A", "capacity": 5000,
        }, format="json")
        assert resp.status_code in (200, 201), resp.data
        assert Farm.objects.filter(farm_code="F100").exists()

    def test_supervisor_cannot_edit_unassigned_farm(self, api, supervisor_user, farm):
        self._login(api, "sup")
        resp = api.patch(f"/api/farms/{farm.id}/", {"name": "Hacked"}, format="json")
        assert resp.status_code in (403, 404)
        farm.refresh_from_db()
        assert farm.name != "Hacked"

    def test_supervisor_can_read_farms(self, api, supervisor_user, farm):
        self._login(api, "sup")
        resp = api.get("/api/farms/")
        assert resp.status_code == 200

    def test_supervisor_can_edit_assigned_region_farm(self, api, supervisor_user, farm):
        supervisor_user.profile.assigned_regions = ["Zone-A"]
        supervisor_user.profile.save()
        self._login(api, "sup")
        resp = api.patch(f"/api/farms/{farm.id}/", {"location": "Shed-2"}, format="json")
        assert resp.status_code in (200, 202), getattr(resp, "data", None)
        farm.refresh_from_db()
        assert farm.location == "Shed-2"


class TestStrippedModulesGone:
    """Guard: the Feeds-only image must not expose chicken/layer/accounting APIs."""
    @pytest.mark.parametrize("path", [
        "/api/chicken/sales/",
        "/api/layer/flocks/",
        "/api/accounting/accounts/",
        "/api/inventory/items/",
    ])
    def test_stripped_endpoints_404(self, auth_admin, path):
        resp = auth_admin.get(path)
        assert resp.status_code == 404
