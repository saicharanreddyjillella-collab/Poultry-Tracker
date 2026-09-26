"""
Seed the default chart of accounts and base units.
Idempotent — safe to run repeatedly. Run once after migrating the accounting app.
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from accounting.models import Account, Unit


DEFAULT_ACCOUNTS = [
    # code, name, type, is_party_control, business
    ('CASH', 'Cash', 'ASSET', False, 'common'),
    ('BANK', 'Bank', 'ASSET', False, 'common'),
    ('UPI', 'UPI', 'ASSET', False, 'common'),
    ('DEBTORS', 'Debtors (Customers)', 'ASSET', True, 'common'),
    ('STOCK', 'Stock in Hand', 'ASSET', False, 'common'),
    ('RAWSTOCK', 'Raw Material Stock', 'ASSET', False, 'feeds'),
    ('FINSTOCK', 'Finished Feed Stock', 'ASSET', False, 'feeds'),

    ('CREDITORS', 'Creditors (Suppliers)', 'LIABILITY', True, 'common'),
    ('FARMERPAY', 'Farmer Payables', 'LIABILITY', True, 'feeds'),

    ('SALES', 'Sales', 'INCOME', False, 'chicken_center'),
    ('EGGSALES', 'Egg Sales', 'INCOME', False, 'layer'),

    ('PURCHASES', 'Purchases', 'EXPENSE', False, 'chicken_center'),
    ('RAWPUR', 'Raw Material Purchases', 'EXPENSE', False, 'feeds'),
    ('TRANSPORT', 'Transport', 'EXPENSE', False, 'common'),
    ('LABOUR', 'Labour', 'EXPENSE', False, 'common'),
    ('ICE', 'Ice', 'EXPENSE', False, 'chicken_center'),
    ('FUEL', 'Fuel', 'EXPENSE', False, 'common'),
    ('WOOD', 'Wood', 'EXPENSE', False, 'common'),
    ('COVERS', 'Covers', 'EXPENSE', False, 'common'),
    ('FOOD', 'Food / Meals', 'EXPENSE', False, 'common'),
    ('STATIONERY', 'Stationery', 'EXPENSE', False, 'common'),
    ('RENT', 'Rent', 'EXPENSE', False, 'common'),
    ('ELECTRICITY', 'Electricity', 'EXPENSE', False, 'common'),
    ('MILLING', 'Milling / Production Overhead', 'EXPENSE', False, 'feeds'),
    ('SHRINKAGE', 'Shrinkage / Mortality Loss', 'EXPENSE', False, 'common'),
    ('MISC', 'Miscellaneous', 'EXPENSE', False, 'common'),

    ('CAPITAL', 'Capital', 'EQUITY', False, 'common'),
    ('OBE', 'Opening Balance Equity', 'EQUITY', False, 'common'),
]


class Command(BaseCommand):
    help = 'Seed default chart of accounts and base units'

    def handle(self, *args, **opts):
        # Base units
        kg, _ = Unit.objects.get_or_create(
            symbol='kg', defaults={'name': 'Kilogram', 'factor_to_base': Decimal('1')})
        if kg.name != 'Kilogram':
            pass
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

        # Accounts
        n_created = 0
        for code, name, atype, ctrl, biz in DEFAULT_ACCOUNTS:
            obj, created = Account.objects.get_or_create(
                code=code,
                defaults={'name': name, 'type': atype,
                          'is_party_control': ctrl, 'business': biz})
            if created:
                n_created += 1
        self.stdout.write(self.style.SUCCESS(
            f'Chart of accounts seeded ({n_created} new, {len(DEFAULT_ACCOUNTS)} total).'))
