"""Who entered a farm's figures: any supervisor can enter for any farm, and every entry,
sale and medicine records who entered it and who changed it last."""
import datetime
import importlib
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import AuditLog, DailyEntry, Farm, Flock, UserProfile

pytestmark = pytest.mark.django_db
T = datetime.date.today()


def login(username, role, regions=(), first=''):
    u = User.objects.create_user(username=username, password='pass12345', first_name=first)
    UserProfile.objects.create(user=u, role=role, assigned_regions=list(regions))
    c = APIClient()
    r = c.post('/api/auth/login/', {'username': username, 'password': 'pass12345'}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


@pytest.fixture
def world(db):
    a = Farm.objects.create(farm_code='A1', name='Lakshmi', owner_name='o', region='Zone-A', capacity=5000)
    fl = Flock.objects.create(farm=a, placement_date=T - datetime.timedelta(days=10), chick_count=1000)
    return {'farm': a, 'flock': fl,
            'ravi': login('ravi', 'supervisor', ['Zone-A'], 'Ravi'),
            'kiran': login('kiran', 'supervisor', ['Zone-B'], 'Kiran'),
            'admin': login('boss', 'admin')}


def test_a_covering_supervisor_enters_and_is_recorded(world):
    fl = world['flock']
    # Kiran (Zone-B) covers Lakshmi (Zone-A) while Ravi is on leave
    r = world['kiran'].post('/api/daily-entries/', {'flock': fl.id, 'date': str(T), 'mortality_count': 3,
                                                    'entered_by': User.objects.get(username='ravi').id},
                            format='json')
    assert r.status_code == 201, r.data
    assert r.data['entered_by_name'] == 'Kiran'                    # can't be set by the client
    e = DailyEntry.objects.get(pk=r.data['id'])
    assert e.entered_by.username == 'kiran' and e.edited_by is None
    # Ravi corrects it later
    r = world['ravi'].patch(f"/api/daily-entries/{e.id}/", {'mortality_count': 4}, format='json')
    assert r.status_code == 200 and r.data['edited_by_name'] == 'Ravi' and r.data['entered_by_name'] == 'Kiran'
    # shown on the flock page's entries and on the dashboard
    rows = world['admin'].get(f'/api/flocks/{fl.id}/cumulative/').data['entries']
    assert rows[-1]['entered_by_name'] == 'Kiran' and rows[-1]['edited_by_name'] == 'Ravi'
    dash = world['admin'].get('/api/dashboard/').data['flock_rows'][0]
    assert dash['last_entry_by'] == 'Kiran'


def test_sales_and_medicines_record_who_entered(world):
    fl = world['flock']
    s = world['kiran'].post('/api/sales/', {'flock': fl.id, 'date': str(T), 'bird_count': 10,
                                            'total_weight_kg': '20', 'trader_name': 't'}, format='json')
    m = world['kiran'].post('/api/medications/', {'flock': fl.id, 'date': str(T), 'name': 'x', 'cost': '1'},
                            format='json')
    assert s.status_code == 201 and s.data['entered_by_name'] == 'Kiran'
    assert m.status_code == 201 and m.data['entered_by_name'] == 'Kiran'
    sale_rows = world['admin'].get(f'/api/flocks/{fl.id}/cumulative/').data['sales']
    assert sale_rows[0]['entered_by_name'] == 'Kiran'
    meds = world['admin'].get(f'/api/flocks/{fl.id}/').data['medications']
    assert meds[0]['entered_by_name'] == 'Kiran'


def test_existing_records_are_filled_in_from_the_change_history(world):
    fl = world['flock']
    ravi, kiran = User.objects.get(username='ravi'), User.objects.get(username='kiran')
    e = DailyEntry.objects.create(flock=fl, date=T, mortality_count=1)        # made before the field existed
    AuditLog.objects.all().delete()
    AuditLog.objects.create(actor=ravi, action='create', model='DailyEntry', object_id=str(e.pk))
    AuditLog.objects.create(actor=kiran, action='update', model='DailyEntry', object_id=str(e.pk))
    migration = importlib.import_module('core.migrations.0036_entered_by')
    migration.backfill_from_history(django_apps, None)
    e.refresh_from_db()
    assert e.entered_by == ravi and e.edited_by == kiran
