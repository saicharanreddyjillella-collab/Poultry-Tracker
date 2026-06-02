from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile


class Command(BaseCommand):
    help = 'Create the initial admin user'

    def handle(self, *args, **options):
        if User.objects.filter(username='admin').exists():
            self.stdout.write(self.style.WARNING('Admin user already exists'))
            return

        user = User.objects.create_superuser(
            username='admin',
            password='admin123',
            first_name='Admin',
        )
        UserProfile.objects.create(user=user, role='admin')
        self.stdout.write(self.style.SUCCESS(
            'Admin user created: username=admin, password=admin123'
        ))
