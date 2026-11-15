"""E7 — Sentry error monitoring: env gating, privacy defaults, end-to-end capture."""
import logging
from unittest import mock

import pytest
import sentry_sdk
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from rest_framework.test import APIClient
from sentry_sdk.transport import Transport


def _val(v):
    """Scrubbed values are AnnotatedValue placeholders until serialisation."""
    return getattr(v, "value", v)

from config import monitoring

DSN = "https://publickey@o0.ingest.sentry.io/1"
SECRET_PAN = "ABCPE1234F"


class TestGating:
    def test_off_without_dsn(self):
        with mock.patch("sentry_sdk.init") as init:
            assert monitoring.init_sentry(False, {}) is False
            assert monitoring.init_sentry(False, {"SENTRY_DSN": "   "}) is False
        init.assert_not_called()

    def test_disabled_in_test_settings(self, settings):
        assert settings.SENTRY_ENABLED is False

    def test_on_with_dsn(self):
        with mock.patch("sentry_sdk.init") as init:
            assert monitoring.init_sentry(False, {"SENTRY_DSN": DSN, "SENTRY_RELEASE": "abc123"}) is True
        opts = init.call_args.kwargs
        assert opts["dsn"] == DSN
        assert opts["environment"] == "production"
        assert opts["release"] == "abc123"
        assert opts["traces_sample_rate"] == 0.0

    def test_environment_defaults_and_override(self):
        assert monitoring.build_options(DSN, True, {})["environment"] == "development"
        assert monitoring.build_options(DSN, False, {"SENTRY_ENVIRONMENT": "staging"})["environment"] == "staging"

    @pytest.mark.parametrize("raw,expected", [
        ("0.25", 0.25), ("1", 1.0), ("5", 1.0), ("-1", 0.0), ("abc", 0.0), (None, 0.0), ("", 0.0),
    ])
    def test_trace_rate_parsing_is_safe(self, raw, expected):
        assert monitoring._sample_rate(raw) == expected


class TestPrivacyDefaults:
    def test_no_pii_and_no_request_bodies(self):
        opts = monitoring.build_options(DSN, False, {})
        assert opts["send_default_pii"] is False
        assert opts["max_request_body_size"] == "never"

    def test_scrubber_filters_pan_and_bank_fields(self):
        scrubber = monitoring.build_options(DSN, False, {})["event_scrubber"]
        event = {
            "extra": {"pan": SECRET_PAN, "farm": {"bank_account": "0001", "ifsc": "SBIN0001"}, "flock": 7},
            "exception": {"values": [{"stacktrace": {"frames": [
                {"vars": {"pan": SECRET_PAN, "password": "x", "net_payable": "100"}}]}}]},
        }
        scrubber.scrub_event(event)
        assert _val(event["extra"]["pan"]) == "[Filtered]"
        assert _val(event["extra"]["farm"]["bank_account"]) == "[Filtered]"
        assert _val(event["extra"]["farm"]["ifsc"]) == "[Filtered]"
        assert event["extra"]["flock"] == 7
        frame = event["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
        assert _val(frame["pan"]) == "[Filtered]" and _val(frame["password"]) == "[Filtered]"
        assert frame["net_payable"] == "100"          # business numbers kept for debugging


class _Capture(Transport):
    def __init__(self):
        super().__init__({"dsn": DSN})
        self.events = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


@pytest.fixture
def live_sentry():
    """Real SDK with a capturing transport (nothing leaves the machine)."""
    cap = _Capture()
    opts = monitoring.build_options(DSN, False, {"SENTRY_RELEASE": "test-sha"})
    sentry_sdk.init(transport=cap, **opts)
    yield cap
    sentry_sdk.flush()
    sentry_sdk.init()   # back to a disabled client for the rest of the suite


@pytest.mark.django_db
class TestEndToEnd:
    def test_unhandled_500_is_captured_without_body(self, live_sentry, admin_user):
        client = APIClient(raise_request_exception=False)
        with mock.patch("core.views.auth.authenticate", side_effect=RuntimeError("db exploded")):
            r = client.post("/api/auth/login/", {"username": "admin", "password": "pass12345", "pan": SECRET_PAN},
                            format="json")
        assert r.status_code == 500
        sentry_sdk.flush()
        assert live_sentry.events, "500 was not reported"
        ev = live_sentry.events[-1]
        assert ev["exception"]["values"][-1]["value"] == "db exploded"
        assert ev["release"] == "test-sha" and ev["environment"] == "production"
        assert ev["transaction"] == "/api/auth/login/"           # which endpoint broke
        assert not ev.get("request", {}).get("data")             # body withheld
        dumped = str(ev)
        assert "pass12345" not in dumped          # request body never sent
        assert SECRET_PAN not in dumped
        assert "user" not in ev or "ip_address" not in ev.get("user", {})

    def test_error_logs_become_events(self, live_sentry):
        logging.getLogger("core.views.health").error("Health check: database unreachable")
        sentry_sdk.flush()
        assert any("database unreachable" in str(e.get("logentry") or e.get("message")) for e in live_sentry.events)

    def test_warnings_are_breadcrumbs_not_events(self, live_sentry):
        logging.getLogger("core").warning("Bill reopened: just a warning")
        sentry_sdk.flush()
        assert not any("just a warning" in str(e) for e in live_sentry.events)


class TestCheckCommand:
    def test_errors_when_disabled(self):
        with pytest.raises(CommandError, match="SENTRY_DSN"):
            call_command("check_monitoring")

    @override_settings(SENTRY_ENABLED=True)
    def test_sends_when_enabled(self, live_sentry, capsys):
        call_command("check_monitoring")
        assert any("monitoring check" in str(e) for e in live_sentry.events)
        assert "Test event sent" in capsys.readouterr().out
