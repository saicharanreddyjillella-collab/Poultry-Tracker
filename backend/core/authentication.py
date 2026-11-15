"""JWT authentication + temporary-password enforcement.

A user whose password was set by an admin (UserProfile.must_change_password)
can only reach the endpoints needed to change it until they do.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

ALLOWED_WHILE_TEMPORARY = (
    '/api/auth/me/',
    '/api/auth/change-password/',
    '/api/auth/logout/',
    '/api/client-errors/',
)


class PasswordChangeRequired(PermissionDenied):
    default_detail = 'You must set your own password before continuing.'
    default_code = 'password_change_required'


class JWTAuthenticationWithPasswordCheck(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        profile = getattr(user, 'profile', None)
        if profile is not None and profile.must_change_password and request.path not in ALLOWED_WHILE_TEMPORARY:
            raise PasswordChangeRequired()
        return user, token
