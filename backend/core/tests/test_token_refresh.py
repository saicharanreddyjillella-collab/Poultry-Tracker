"""E15 — silent token refresh: refresh endpoint, rotation, revocation."""
import datetime

import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.settings import api_settings

from core.models import UserProfile

pytestmark = pytest.mark.django_db
REFRESH = "/api/auth/token/refresh/"


@pytest.fixture
def tokens(api, admin_user):
    r = api.post("/api/auth/login/", {"username": "admin", "password": "pass12345"}, format="json")
    return r.data


def _me(access):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return c.get("/api/auth/me/")


def _refresh(token):
    return APIClient().post(REFRESH, {"refresh": token}, format="json")


class TestConfig:
    def test_access_is_short_lived_refresh_slides(self):
        assert api_settings.ACCESS_TOKEN_LIFETIME == datetime.timedelta(minutes=30)
        assert api_settings.REFRESH_TOKEN_LIFETIME == datetime.timedelta(days=7)
        assert api_settings.ROTATE_REFRESH_TOKENS and api_settings.BLACKLIST_AFTER_ROTATION


class TestRefresh:
    def test_refresh_returns_working_access_and_rotated_refresh(self, tokens):
        r = _refresh(tokens["refresh"])
        assert r.status_code == 200
        assert r.data["access"] != tokens["access"]
        assert r.data["refresh"] != tokens["refresh"]
        assert _me(r.data["access"]).status_code == 200

    def test_old_refresh_is_dead_after_rotation(self, tokens):
        assert _refresh(tokens["refresh"]).status_code == 200
        r = _refresh(tokens["refresh"])             # replay of a used token
        assert r.status_code == 401 and r.data["code"] == "token_not_valid"

    def test_rotated_chain_keeps_working(self, tokens):
        rt = tokens["refresh"]
        for _ in range(3):
            r = _refresh(rt)
            assert r.status_code == 200
            rt = r.data["refresh"]

    @pytest.mark.parametrize("bad", ["", "garbage", "a.b.c"])
    def test_malformed_token_is_401(self, bad):
        assert _refresh(bad).status_code in (400, 401)

    def test_access_token_cannot_be_used_as_refresh(self, tokens):
        assert _refresh(tokens["access"]).status_code == 401

    def test_inactive_user_cannot_refresh(self, tokens, admin_user):
        admin_user.is_active = False
        admin_user.save()
        assert _refresh(tokens["refresh"]).status_code == 401

    def test_deleted_user_gets_401_not_500(self, api):
        u = User.objects.create_user("temp", password="pass12345")
        UserProfile.objects.create(user=u, role="supervisor")
        rt = api.post("/api/auth/login/", {"username": "temp", "password": "pass12345"},
                      format="json").data["refresh"]
        u.delete()
        assert _refresh(rt).status_code == 401

    @override_settings(SIMPLE_JWT={"REFRESH_TOKEN_LIFETIME": datetime.timedelta(seconds=-1)})
    def test_expired_refresh_is_401(self, admin_user):
        from rest_framework_simplejwt.tokens import RefreshToken
        rt = RefreshToken.for_user(admin_user)
        rt.set_exp(lifetime=datetime.timedelta(seconds=-10))
        assert _refresh(str(rt)).status_code == 401

    def test_throttled(self, tokens):
        codes = [_refresh("x").status_code for _ in range(62)]
        assert codes[-1] == 429


class TestLogout:
    def test_logout_revokes_refresh(self, tokens):
        r = APIClient().post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
        assert r.status_code == 200
        assert _refresh(tokens["refresh"]).status_code == 401

    def test_logout_is_idempotent_and_needs_no_access_token(self, tokens):
        c = APIClient()
        assert c.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json").status_code == 200
        assert c.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json").status_code == 200
        assert c.post("/api/auth/logout/", {}, format="json").status_code == 200
        assert c.post("/api/auth/logout/", {"refresh": "junk"}, format="json").status_code == 200


class TestPasswordChangeRevokes:
    def test_change_password_returns_fresh_tokens_and_kills_other_sessions(self, api, admin_user):
        login = lambda: api.post("/api/auth/login/", {"username": "admin", "password": "pass12345"},
                                 format="json").data
        other_device = login()
        this_device = login()
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {this_device['access']}")
        r = c.post("/api/auth/change-password/",
                   {"current_password": "pass12345", "new_password": "N3w-strong-pass!"}, format="json")
        assert r.status_code == 200
        # BUG-006: the page stores these — they must be real tokens
        assert r.data["access"] and r.data["refresh"]
        assert _me(r.data["access"]).status_code == 200
        assert _refresh(r.data["refresh"]).status_code == 200
        # every pre-existing session is revoked
        assert _refresh(other_device["refresh"]).status_code == 401
        assert _refresh(this_device["refresh"]).status_code == 401

    def test_admin_password_reset_signs_user_out(self, auth_admin, api):
        u = User.objects.create_user("sup2", password="pass12345")
        UserProfile.objects.create(user=u, role="supervisor")
        rt = APIClient().post("/api/auth/login/", {"username": "sup2", "password": "pass12345"},
                              format="json").data["refresh"]
        r = auth_admin.put(f"/api/auth/users/{u.id}/", {"password": "An0ther-strong!"}, format="json")
        assert r.status_code == 200
        assert _refresh(rt).status_code == 401

    def test_admin_profile_edit_without_password_keeps_sessions(self, auth_admin):
        u = User.objects.create_user("sup3", password="pass12345")
        UserProfile.objects.create(user=u, role="supervisor")
        rt = APIClient().post("/api/auth/login/", {"username": "sup3", "password": "pass12345"},
                              format="json").data["refresh"]
        auth_admin.put(f"/api/auth/users/{u.id}/", {"first_name": "Ravi"}, format="json")
        assert _refresh(rt).status_code == 200
