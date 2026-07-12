from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from ..models import UserProfile, Farm


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
    if len(password) < 8:
        return Response({'error': 'Password must be at least 8 characters'}, status=400)

    user = User.objects.create_user(username=username, password=password,
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
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if not user:
        return Response({'error': 'Invalid credentials'}, status=401)

    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': _user_data(user),
    })


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
    if len(new) < 8:
        return Response({'error': 'New password must be at least 8 characters'}, status=400)
    user.set_password(new)
    user.save()
    return Response({'message': 'Password changed'})


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

    user = User.objects.create_user(username=username, password=password,
                                     first_name=first_name, last_name=last_name)
    profile = UserProfile.objects.create(user=user, role=role, phone=phone, assigned_regions=assigned_regions)
    if assigned_farm_ids:
        profile.assigned_farms.set(assigned_farm_ids)
    profile.sync_farms_from_regions()

    return Response({'message': f'User {username} created'}, status=201)


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
        user.set_password(request.data['password'])
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
    }
