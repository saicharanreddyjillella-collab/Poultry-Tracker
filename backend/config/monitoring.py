"""E7 — Error monitoring (Sentry), env-gated.

Off unless SENTRY_DSN is set, so dev, tests and CI never send anything.
Privacy defaults suit a settlement system holding grower PAN/bank details:
  * send_default_pii=False   — no user IPs, cookies or usernames
  * max_request_body_size='never' — request bodies (bills, PAN, amounts) never leave
  * EventScrubber with an extended denylist (pan, account, ifsc, ...) for
    stack-frame locals and extra data.
Unhandled exceptions and ERROR-level log records become Sentry events.

Env:
  SENTRY_DSN                  enable + where to send
  SENTRY_ENVIRONMENT          default: production (DEBUG=False) / development
  SENTRY_RELEASE              e.g. a git SHA, to tie errors to a deploy
  SENTRY_TRACES_SAMPLE_RATE   performance tracing, 0.0–1.0 (default 0 = off)
"""
import logging

logger = logging.getLogger(__name__)

# Keys scrubbed from events in addition to sentry's defaults (password, token...).
EXTRA_DENYLIST = [
    'pan', 'pan_number', 'gstin', 'aadhaar', 'account', 'account_number',
    'bank_account', 'ifsc', 'upi', 'phone', 'mobile', 'refresh', 'access',
    'secret_key', 'database_url',
]


def _sample_rate(raw):
    try:
        rate = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return min(max(rate, 0.0), 1.0)


def build_options(dsn, debug, env):
    """sentry_sdk.init kwargs for this deployment (pure: easy to test)."""
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.scrubber import EventScrubber, DEFAULT_DENYLIST

    return dict(
        dsn=dsn,
        environment=env.get('SENTRY_ENVIRONMENT') or ('development' if debug else 'production'),
        release=env.get('SENTRY_RELEASE') or None,
        traces_sample_rate=_sample_rate(env.get('SENTRY_TRACES_SAMPLE_RATE', '0')),
        send_default_pii=False,
        max_request_body_size='never',
        event_scrubber=EventScrubber(denylist=DEFAULT_DENYLIST + EXTRA_DENYLIST, recursive=True),
        integrations=[
            DjangoIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )


def init_sentry(debug, env):
    """Initialise Sentry if SENTRY_DSN is set. Returns True when enabled."""
    dsn = (env.get('SENTRY_DSN') or '').strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:  # pragma: no cover - sentry-sdk is pinned in requirements
        logger.warning('SENTRY_DSN is set but sentry-sdk is not installed; monitoring disabled.')
        return False
    sentry_sdk.init(**build_options(dsn, debug, env))
    return True
