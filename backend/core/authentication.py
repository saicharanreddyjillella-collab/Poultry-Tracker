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


# The other businesses (Chicken Center, Layer Farm) and their shared accounting /
# inventory books are admin-only for now: Feeds supervisors and the feed mill
# must not read or change another business's sales, payments or P&L.
ADMIN_ONLY_PREFIXES = ('/api/chicken/', '/api/layer/', '/api/accounting/', '/api/inventory/')


# Company feed prices: admin and the feed mill only — not supervisors.
COMPANY_PRICE_PREFIXES = ('/api/feed-rates/',)


class CompanyPricesHidden(PermissionDenied):
    default_detail = 'Feed prices are visible to the admin only.'
    default_code = 'company_prices_hidden'


class OtherBusinessAdminOnly(PermissionDenied):
    default_detail = 'Only an admin can access this business.'
    default_code = 'business_admin_only'


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
        if request.path.startswith(ADMIN_ONLY_PREFIXES) and not (
                (profile is not None and profile.is_admin) or (profile is None and user.is_superuser)):
            raise OtherBusinessAdminOnly()
        if request.path.startswith(COMPANY_PRICE_PREFIXES) and profile is not None and profile.role == 'supervisor':
            raise CompanyPricesHidden()
        return user, token
