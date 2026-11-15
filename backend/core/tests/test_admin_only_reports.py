"""Owner View, Break-even and Feed Forecast are business-sensitive: admin only."""
import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import UserProfile

pytestmark = pytest.mark.django_db
URLS = ["/api/reports/owner-dashboard/", "/api/reports/break-even/", "/api/reports/feed-forecast/"]


def _client(role):
    u = User.objects.create_user(f"u_{role}", password="pass12345")
    UserProfile.objects.create(user=u, role=role)
    c = APIClient()
    tok = c.post("/api/auth/login/", {"username": u.username, "password": "pass12345"}, format="json").data["access"]
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tok}")
    return c


@pytest.mark.parametrize("url", URLS)
def test_admin_can_view(auth_admin, url):
    assert auth_admin.get(url).status_code == 200


@pytest.mark.parametrize("role", ["supervisor", "plant"])
@pytest.mark.parametrize("url", URLS)
def test_other_roles_are_refused(role, url):
    r = _client(role).get(url)
    assert r.status_code == 403


@pytest.mark.parametrize("url", URLS)
def test_anonymous_is_refused(url):
    assert APIClient().get(url).status_code == 401


def test_supervisor_still_has_normal_reports(farm):
    c = _client("supervisor")
    assert c.get("/api/dashboard/").status_code == 200
