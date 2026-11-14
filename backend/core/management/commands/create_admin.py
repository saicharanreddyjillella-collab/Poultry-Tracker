import os

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from core.models import UserProfile


class Command(BaseCommand):
    help = 'Create the initial admin user (password via --password or ADMIN_PASSWORD env)'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin')
        parser.add_argument('--password', default=None,
                            help='Admin password; falls back to the ADMIN_PASSWORD env var')
        parser.add_argument('--first-name', default='Admin')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password'] or os.environ.get('ADMIN_PASSWORD')
        if not password:
            raise CommandError(
                'No password provided. Pass --password or set ADMIN_PASSWORD. '
                'A default password is not used for security reasons.'
            )
        try:
            validate_password(password)
        except ValidationError as e:
            raise CommandError('Weak password: ' + ' '.join(e.messages))

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists'))
            return

        user = User.objects.create_superuser(
            username=username, password=password, first_name=options['first_name'],
        )
        UserProfile.objects.create(user=user, role='admin')
        self.stdout.write(self.style.SUCCESS(
            f'Admin user "{username}" created.'  # never echo the password
        ))
