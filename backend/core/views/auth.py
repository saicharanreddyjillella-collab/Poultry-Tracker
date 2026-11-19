from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from ..models import UserProfile, Farm


# ── E15: token lifecycle ───────────────────────────────────────────────────
def _issue_tokens(user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


def revoke_all_tokens(user):
    """Blacklist every outstanding refresh token for this user (signs them
    out everywhere once their current access token expires)."""
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
    for tok in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=tok)


def _password_error(password, user=None):
    """Run Django's configured password validators. Returns a joined error
    string if the password is weak, else None."""
    try:
        validate_password(password, user=user)
        return None
    except DjangoValidationError as e:
        return ' '.join(e.messages)


@api_view(['GET'])
@permission_classes([AllowAny])
def check_setup(request):
    needs_setup = not User.objects.exists()
    return Response({'needs_setup': needs_setup})


@api_view(['POST'])
@permission_classes([AllowAny])
def initial_setup(request):
    if User.objects.exists():
        return Response({'error': 'Setup already completed.'}, status=403)

    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')

    if not username or not password:
        return Response({'error': 'Username and password are required'}, status=400)
    pw_err = _password_error(password)
    if pw_err:
        return Response({'error': pw_err}, status=400)

    # The first account owns the system: also give it Django-admin access, the
    # same as `manage.py create_admin` does on the server.
    user = User.objects.create_superuser(username=username, password=password,
                                         first_name=first_name, last_name=last_name)
    UserProfile.objects.create(user=user, role='admin')

    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return Response({
        'message': 'Admin account created successfully',
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': _user_data(user),
    }, status=201)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': 'Invalid credentials'}, status=401)

    from django.contrib.auth.models import update_last_login
    from rest_framework_simplejwt.tokens import RefreshToken
    update_last_login(None, user)                      # shown on the admin's System Health page
    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': _user_data(user),
    })


# ScopedRateThrottle reads throttle_scope from the view; for @api_view
# function views it must be set as an attribute on the wrapped view.
login_view.cls.throttle_scope = 'login'


@api_view(['GET'])
def me_view(request):
    return Response(_user_data(request.user))


@api_view(['POST'])
def change_password(request):
    user = request.user
    current = request.data.get('current_password')
    new = request.data.get('new_password')
    if not user.check_password(current):
        return Response({'error': 'Current password is incorrect'}, status=400)
    if new == current:
        return Response({'error': 'Choose a new password different from the current one'}, status=400)
    pw_err = _password_error(new, user=user)
    if pw_err:
        return Response({'error': pw_err}, status=400)
    user.set_password(new)
    user.save()
    # Sign out every other session, keep this one with fresh tokens.
    revoke_all_tokens(user)
    if hasattr(user, 'profile') and user.profile.must_change_password:
        user.profile.must_change_password = False
        user.profile.save(update_fields=['must_change_password'])
    return Response({'message': 'Password changed', **_issue_tokens(user), 'user': _user_data(user)})


@api_view(['GET', 'POST'])
def manage_users(request):
    if not request.user.profile.is_admin:
        return Response({'error': 'Admin only'}, status=403)

    if request.method == 'GET':
        users = User.objects.select_related('profile').all()
        return Response([{
            'id': u.id,
            'username': u.username,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'role': u.profile.role if hasattr(u, 'profile') else 'admin',
            'phone': u.profile.phone if hasattr(u, 'profile') else '',
            'assigned_farm_ids': list(u.profile.assigned_farms.values_list('id', flat=True)) if hasattr(u, 'profile') else [],
            'assigned_regions': u.profile.assigned_regions if hasattr(u, 'profile') else [],
            'must_change_password': u.profile.must_change_password if hasattr(u, 'profile') else False,
        } for u in users])

    # POST — create user
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '')
    role = request.data.get('role', 'supervisor')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')
    phone = request.data.get('phone', '')
    assigned_farm_ids = request.data.get('assigned_farm_ids', [])
    assigned_regions = request.data.get('assigned_regions', [])

    if User.objects.filter(username=username).exists():
        return Response({'error': 'Username already exists'}, status=400)
    pw_err = _password_error(password)
    if pw_err:
        return Response({'error': pw_err}, status=400)

    user = User.objects.create_user(username=username, password=password,
                                     first_name=first_name, last_name=last_name)
    # Admin chose this password → it's temporary until the user sets their own.
    profile = UserProfile.objects.create(user=user, role=role, phone=phone, assigned_regions=assigned_regions,
                                         must_change_password=True)
    if assigned_farm_ids:
        profile.assigned_farms.set(assigned_farm_ids)
    profile.sync_farms_from_regions()

    return Response({'message': f'User {username} created', 'id': user.id}, status=201)


@api_view(['PUT', 'DELETE'])
def manage_user_detail(request, user_id):
    if not request.user.profile.is_admin:
        return Response({'error': 'Admin only'}, status=403)
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    if request.method == 'DELETE':
        user.delete()
        return Response({'message': 'User deleted'})

    # PUT — update
    user.first_name = request.data.get('first_name', user.first_name)
    user.last_name = request.data.get('last_name', user.last_name)
    if request.data.get('password'):
        pw_err = _password_error(request.data['password'], user=user)
        if pw_err:
            return Response({'error': pw_err}, status=400)
        user.set_password(request.data['password'])
        revoke_all_tokens(user)   # admin reset → that user is signed out everywhere
        if hasattr(user, 'profile') and user != request.user:
            user.profile.must_change_password = True   # temporary password
            user.profile.save(update_fields=['must_change_password'])
    user.save()

    if hasattr(user, 'profile'):
        user.profile.role = request.data.get('role', user.profile.role)
        user.profile.phone = request.data.get('phone', user.profile.phone)
        if 'assigned_farm_ids' in request.data:
            user.profile.assigned_farms.set(request.data['assigned_farm_ids'])
        if 'assigned_regions' in request.data:
            user.profile.assigned_regions = request.data['assigned_regions']
        user.profile.save()
        user.profile.sync_farms_from_regions()

    return Response({'message': 'User updated'})


@api_view(['GET'])
def list_regions(request):
    regions = list(Farm.objects.exclude(region='').values_list('region', flat=True).distinct().order_by('region'))
    return Response(regions)


def _user_data(user):
    profile = getattr(user, 'profile', None)
    return {
        'id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': profile.role if profile else 'admin',
        'phone': profile.phone if profile else '',
        'assigned_farm_ids': list(profile.assigned_farms.values_list('id', flat=True)) if profile else [],
        'assigned_regions': profile.assigned_regions if profile else [],
        'must_change_password': bool(profile and profile.must_change_password),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ScopedRateThrottle])
def token_refresh(request):
    """E15: exchange a refresh token for a new access token (+ rotated refresh).

    401 when the refresh token is expired, blacklisted, malformed, or its user
    no longer exists / is inactive — the frontend then signs the user out.
    """
    from rest_framework_simplejwt.serializers import TokenRefreshSerializer
    from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
    from rest_framework.exceptions import AuthenticationFailed
    serializer = TokenRefreshSerializer(data=request.data)
    try:
        serializer.is_valid(raise_exception=True)
    except (TokenError, InvalidToken, AuthenticationFailed, User.DoesNotExist):
        return Response({'detail': 'Session expired. Please log in again.', 'code': 'token_not_valid'},
                        status=401)
    return Response(serializer.validated_data)


token_refresh.cls.throttle_scope = 'token_refresh'


@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    """E15: revoke the given refresh token. Idempotent; works with an expired
    access token (so logout always succeeds from the user's point of view)."""
    from rest_framework_simplejwt.tokens import RefreshToken
    from rest_framework_simplejwt.exceptions import TokenError
    token = request.data.get('refresh')
    if token:
        try:
            RefreshToken(token).blacklist()
        except TokenError:
            pass  # already expired/blacklisted — nothing to revoke
    return Response({'message': 'Logged out'})
