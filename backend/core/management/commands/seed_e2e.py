"""Fixed dataset for the browser (end-to-end) test suite.

    DEBUG=True E2E_SEED=1 python manage.py seed_e2e

WIPES the database first, so it refuses to run unless DEBUG is on AND
E2E_SEED=1 is set — it can never run against a real deployment.

Everyone's password is E2E_PASSWORD below, except `newbie` (a supervisor whose
admin-set password must be changed at first login).
"""
import datetime
import os
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

E2E_PASSWORD = 'E2e-pass-2026!'
NEWBIE_PASSWORD = 'Temp-pass-2026'


class Command(BaseCommand):
    help = 'Wipe the database and load the fixed browser-test dataset (DEBUG + E2E_SEED=1 only).'

    def handle(self, *args, **options):
        if not settings.DEBUG or os.environ.get('E2E_SEED') != '1':
            raise CommandError('Refusing: seed_e2e wipes the database. Needs DEBUG=True and E2E_SEED=1.')

        call_command('flush', '--noinput', verbosity=0)

        from core.billing import generate_bill
        from core.models import (BillConfig, DailyEntry, Farm, FeedOrder, FeedRate, Flock,
                                 Medication, Sale, UserProfile)

        def user(username, role, regions=(), first='', must_change=False, password=E2E_PASSWORD):
            make = User.objects.create_superuser if role == 'admin' else User.objects.create_user
            u = make(username=username, password=password, first_name=first)
            p = UserProfile.objects.create(user=u, role=role, assigned_regions=list(regions),
                                           must_change_password=must_change)
            return u, p

        today = datetime.date.today()
        BillConfig.get_active()
        for ft, rate in (('BPSC', '48'), ('BSC', '46'), ('BFP', '44')):
            FeedRate.objects.create(week_start_date=today - datetime.timedelta(days=today.weekday()),
                                    feed_type=ft, rate_per_kg=Decimal(rate))

        A1 = Farm.objects.create(farm_code='A1', name='Lakshmi Farm', owner_name='Ramesh', region='Zone-A',
                                 capacity=10000, pan='ABCPR1234A')
        A2 = Farm.objects.create(farm_code='A2', name='Ganga Farm', owner_name='Suresh', region='Zone-A',
                                 capacity=10000)
        A3 = Farm.objects.create(farm_code='A3', name='Krishna Farm', owner_name='Mahesh', region='Zone-A',
                                 capacity=10000)
        B1 = Farm.objects.create(farm_code='B1', name='Venkat Farm', owner_name='Venkat', region='Zone-B',
                                 capacity=10000)

        admin, _ = user('admin', 'admin', first='Sai')
        _, pa = user('sup_a', 'supervisor', ['Zone-A'], first='Ravi')
        _, pb = user('sup_b', 'supervisor', ['Zone-B'], first='Kiran')
        user('mill', 'plant', first='Mill')
        _, pn = user('newbie', 'supervisor', ['Zone-A'], first='Naveen', must_change=True,
                     password=NEWBIE_PASSWORD)
        for p in (pa, pb, pn):
            p.sync_farms_from_regions()

        def flock(farm, days_ago, chicks, status='active'):
            return Flock.objects.create(farm=farm, placement_date=today - datetime.timedelta(days=days_ago),
                                        chick_count=chicks, status=status)

        def delivered(farm, fl, bags, feed_type='BFP'):
            FeedOrder.objects.create(farm=farm, flock=fl, feed_type=feed_type, quantity_bags=bags, status='delivered')

        # A1: active flock with feed in stock (daily entries need stock).
        fa1 = flock(A1, 20, 5000)
        delivered(A1, fa1, 200)
        delivered(A1, fa1, 100, 'BSC')
        for d in range(1, 4):
            DailyEntry.objects.create(flock=fa1, date=fa1.placement_date + datetime.timedelta(days=d),
                                      mortality_count=3, feed_bfp_bags=Decimal('5'))
        Medication.objects.create(flock=fa1, name='Vitamin C', date=fa1.placement_date, cost=Decimal('800'))
        FeedOrder.objects.create(farm=A1, flock=fa1, feed_type='BFP', quantity_bags=40)       # pending

        # A2: closed and billed (settlement locked).
        fa2 = flock(A2, 70, 4000, status='closed')
        delivered(A2, fa2, 160)
        for d in range(1, 6):
            DailyEntry.objects.create(flock=fa2, date=fa2.placement_date + datetime.timedelta(days=d),
                                      mortality_count=4, feed_bfp_bags=Decimal('30'))
        Sale.objects.create(flock=fa2, date=fa2.placement_date + datetime.timedelta(days=40), bird_count=3980,
                            total_weight_kg=Decimal('8200'), rate_per_kg=Decimal('105'), trader_name='Balaji Traders')
        generate_bill(fa2, admin)

        # A3: active, all birds sold — ready to close and bill.
        fa3 = flock(A3, 42, 3000)
        delivered(A3, fa3, 120)
        for d in range(1, 6):
            DailyEntry.objects.create(flock=fa3, date=fa3.placement_date + datetime.timedelta(days=d),
                                      mortality_count=2, feed_bfp_bags=Decimal('20'))
        Sale.objects.create(flock=fa3, date=today - datetime.timedelta(days=1), bird_count=2990,
                            total_weight_kg=Decimal('6100'), rate_per_kg=Decimal('102'), trader_name='Sri Traders')

        # B1: another region's active flock + pending order.
        fb1 = flock(B1, 15, 6000)
        delivered(B1, fb1, 150)
        DailyEntry.objects.create(flock=fb1, date=fb1.placement_date + datetime.timedelta(days=1),
                                  mortality_count=5, feed_bfp_bags=Decimal('6'))
        FeedOrder.objects.create(farm=B1, flock=fb1, feed_type='BSC', quantity_bags=25)        # pending

        self.stdout.write(self.style.SUCCESS(
            f'E2E data loaded: farms A1 A2(billed) A3(ready to bill) B1; users admin sup_a sup_b mill newbie; '
            f'flocks A1={fa1.id} A2={fa2.id} A3={fa3.id} B1={fb1.id}'))
