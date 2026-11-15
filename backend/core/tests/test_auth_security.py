"""E2/E3: password policy + login throttle."""
import pytest

pytestmark = pytest.mark.django_db


class TestPasswordPolicy:
    def test_setup_rejects_weak_password(self, api):
        # all-numeric + short -> rejected
        resp = api.post("/api/auth/setup/", {"username": "boss", "password": "1234"}, format="json")
        assert resp.status_code == 400

    def test_setup_rejects_common_password(self, api):
        resp = api.post("/api/auth/setup/", {"username": "boss", "password": "password"}, format="json")
        assert resp.status_code == 400

    def test_setup_accepts_strong_password(self, api):
        resp = api.post("/api/auth/setup/", {"username": "boss", "password": "Str0ng!Pass9"}, format="json")
        assert resp.status_code in (200, 201), resp.data

    def test_setup_admin_can_use_django_admin(self, api):
        from django.contrib.auth.models import User
        api.post("/api/auth/setup/", {"username": "boss", "password": "Str0ng!Pass9"}, format="json")
        u = User.objects.get(username="boss")
        assert u.is_staff and u.is_superuser and u.profile.role == "admin"

    def test_change_password_rejects_weak(self, auth_admin, admin_user):
        resp = auth_admin.post("/api/auth/change-password/", {
            "current_password": "pass12345", "new_password": "12345678",  # all numeric
        }, format="json")
        assert resp.status_code == 400

    def test_change_password_accepts_strong(self, auth_admin, admin_user):
        resp = auth_admin.post("/api/auth/change-password/", {
            "current_password": "pass12345", "new_password": "N3w!Strong2026",
        }, format="json")
        assert resp.status_code == 200, resp.data

    def test_admin_create_user_rejects_weak(self, auth_admin, admin_user):
        resp = auth_admin.post("/api/auth/users/", {
            "username": "sup1", "password": "1111", "role": "supervisor",
        }, format="json")
        assert resp.status_code == 400


class TestLoginThrottle:
    def test_login_throttled_after_limit(self, api, admin_user):
        # login rate is 10/min; the 11th attempt should be throttled (429)
        statuses = []
        for _ in range(12):
            r = api.post("/api/auth/login/", {"username": "admin", "password": "wrong"}, format="json")
            statuses.append(r.status_code)
        assert 429 in statuses, f"expected a 429 within attempts, got {statuses}"
