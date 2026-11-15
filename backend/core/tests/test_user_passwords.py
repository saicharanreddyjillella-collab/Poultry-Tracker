"""Admin-created users: temporary password → user must set their own at first login."""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db
TEMP = "Kp7m-Qx4t-Rw9a"
OWN = "Suresh-own-pass-2026"


def login(username, password):
    c = APIClient()
    r = c.post("/api/auth/login/", {"username": username, "password": password}, format="json")
    if r.status_code == 200:
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c, r


@pytest.fixture
def created(auth_admin):
    r = auth_admin.post("/api/auth/users/", {"username": "suresh", "password": TEMP, "role": "supervisor",
                                             "first_name": "Suresh"}, format="json")
    assert r.status_code == 201, r.data
    return r.data["id"]


def test_supervisor_can_log_in_with_the_password_the_admin_set(created):
    _, r = login("suresh", TEMP)
    assert r.status_code == 200
    assert r.data["user"]["role"] == "supervisor"
    assert r.data["user"]["must_change_password"] is True


def test_admin_list_shows_temporary_flag(auth_admin, created):
    row = next(u for u in auth_admin.get("/api/auth/users/").data if u["username"] == "suresh")
    assert row["must_change_password"] is True


def test_temporary_password_only_allows_changing_it(created):
    c, _ = login("suresh", TEMP)
    r = c.get("/api/farms/")
    assert r.status_code == 403 and r.data["detail"].code == "password_change_required"
    assert c.get("/api/auth/me/").status_code == 200                    # still allowed


def test_after_changing_password_everything_works(created):
    c, _ = login("suresh", TEMP)
    r = c.post("/api/auth/change-password/", {"current_password": TEMP, "new_password": OWN}, format="json")
    assert r.status_code == 200
    assert r.data["user"]["must_change_password"] is False
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    assert c.get("/api/farms/").status_code == 200
    _, r = login("suresh", TEMP)
    assert r.status_code == 401                                           # temp password is gone
    _, r = login("suresh", OWN)
    assert r.status_code == 200 and r.data["user"]["must_change_password"] is False


def test_cannot_reuse_the_temporary_password(created):
    c, _ = login("suresh", TEMP)
    r = c.post("/api/auth/change-password/", {"current_password": TEMP, "new_password": TEMP}, format="json")
    assert r.status_code == 400


def test_admin_reset_makes_password_temporary_again(auth_admin, created):
    c, _ = login("suresh", TEMP)
    c.post("/api/auth/change-password/", {"current_password": TEMP, "new_password": OWN}, format="json")
    r = auth_admin.put(f"/api/auth/users/{created}/", {"password": "Reset-Temp-2026"}, format="json")
    assert r.status_code == 200
    _, r = login("suresh", "Reset-Temp-2026")
    assert r.status_code == 200 and r.data["user"]["must_change_password"] is True


def test_admin_editing_details_without_password_keeps_flag_off(auth_admin, created):
    c, _ = login("suresh", TEMP)
    c.post("/api/auth/change-password/", {"current_password": TEMP, "new_password": OWN}, format="json")
    auth_admin.put(f"/api/auth/users/{created}/", {"first_name": "Suresh K"}, format="json")
    assert User.objects.get(pk=created).profile.must_change_password is False


def test_first_time_setup_admin_is_not_forced(api):
    r = api.post("/api/auth/setup/", {"username": "boss", "password": "Str0ng!Pass9"}, format="json")
    assert r.data["user"]["must_change_password"] is False


def test_weak_password_is_rejected_with_a_reason(auth_admin):
    r = auth_admin.post("/api/auth/users/", {"username": "ravi", "password": "ravi123", "role": "supervisor"},
                        format="json")
    assert r.status_code == 400 and "too short" in r.data["error"]
    assert not User.objects.filter(username="ravi").exists()
