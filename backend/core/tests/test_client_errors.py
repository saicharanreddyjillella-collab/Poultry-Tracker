"""E12 — /api/client-errors/ receives frontend crash reports."""
import logging

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db
URL = "/api/client-errors/"
REPORT = {"message": "kaboom in FlockDetail", "stack": "Error: kaboom\n at Bomb", "component_stack": "at Bomb",
          "source": "boundary", "path": "/flocks/7", "release": "abc123"}


def test_anonymous_report_is_logged_at_error(caplog):
    with caplog.at_level(logging.ERROR, logger="core.client_errors"):
        r = APIClient().post(URL, REPORT, format="json")
    assert r.status_code == 204
    rec = [x for x in caplog.records if x.name == "core.client_errors"][-1]
    assert rec.levelno == logging.ERROR
    assert "kaboom in FlockDetail" in rec.getMessage() and "/flocks/7" in rec.getMessage()
    assert rec.client_stack.startswith("Error: kaboom")
    assert rec.client_user_id is None


def test_logged_in_user_id_is_attached(auth_admin, admin_user, caplog):
    with caplog.at_level(logging.ERROR, logger="core.client_errors"):
        assert auth_admin.post(URL, REPORT, format="json").status_code == 204
    assert caplog.records[-1].client_user_id == admin_user.id


def test_fields_are_size_capped(caplog):
    big = dict(REPORT, message="m" * 5000, stack="s" * 50000, path="/p" * 1000)
    with caplog.at_level(logging.ERROR, logger="core.client_errors"):
        assert APIClient().post(URL, big, format="json").status_code == 204
    rec = caplog.records[-1]
    assert len(rec.client_stack) == 4000
    assert "m" * 501 not in rec.getMessage()


@pytest.mark.parametrize("payload", [{}, {"message": ""}, ["not", "a", "dict"]])
def test_rejects_empty_or_malformed(payload):
    assert APIClient().post(URL, payload, format="json").status_code == 400


def test_get_not_allowed():
    assert APIClient().get(URL).status_code == 405


def test_throttled_per_ip():
    c = APIClient()
    codes = [c.post(URL, REPORT, format="json").status_code for _ in range(32)]
    assert codes[:30] == [204] * 30
    assert codes[-1] == 429
