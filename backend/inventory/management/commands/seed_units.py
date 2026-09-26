"""
Seed base units of measure. Idempotent.
Run after migrating: python manage.py seed_units
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from inventory.models import Unit


class Command(BaseCommand):
    help = 'Seed base units (kg, bag=50kg, tonne, piece)'

    def handle(self, *args, **opts):
        kg, _ = Unit.objects.get_or_create(
            symbol='kg', defaults={'name': 'Kilogram', 'factor_to_base': Decimal('1')})

        bag, created = Unit.objects.get_or_create(
            symbol='bag',
            defaults={'name': 'Bag (50 kg)', 'base_unit': kg, 'factor_to_base': Decimal('50')})
        if not created and bag.base_unit_id != kg.id:
            bag.base_unit = kg
            bag.factor_to_base = Decimal('50')
            bag.save()

        Unit.objects.get_or_create(
            symbol='tonne',
            defaults={'name': 'Tonne (1000 kg)', 'base_unit': kg, 'factor_to_base': Decimal('1000')})
        Unit.objects.get_or_create(
            symbol='pc', defaults={'name': 'Piece', 'factor_to_base': Decimal('1')})

        self.stdout.write(self.style.SUCCESS('Units seeded (kg, bag=50kg, tonne, pc).'))
