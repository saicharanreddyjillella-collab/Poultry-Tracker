"""Expose the current request's user to code that has no request (signals)."""
import threading

_local = threading.local()


def get_current_user():
    return getattr(_local, 'user', None)


def set_current_user(user):
    _local.user = user


class CurrentUserMiddleware:
    """Stores request.user in a thread-local for the duration of the request.

    DRF authenticates (JWT) inside the view, after middleware runs, so we also
    let the audit layer fall back to request.user resolved lazily — see
    core/audit.py. This middleware captures session-authenticated users and
    clears state after each request.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_user(getattr(request, 'user', None))
        _local.request = request
        try:
            return self.get_response(request)
        finally:
            _local.user = None
            _local.request = None


def get_current_request():
    return getattr(_local, 'request', None)
