"""Feed types are an admin-managed list: add BFP2, rename BFP → BFP1, retire, reorder.
Records keep the permanent key, so renames never break history."""
import datetime
import importlib
from decimal import Decimal

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import DailyEntry, Farm, FeedOrder, FeedType, Flock, UserProfile

pytestmark = pytest.mark.django_db
T = datetime.date.today()


def login(username, role):
    u = User.objects.create_user(username=username, password='pass12345')
    UserProfile.objects.create(user=u, role=role, assigned_regions=['Zone-A'])
    c = APIClient()
    r = c.post('/api/auth/login/', {'username': username, 'password': 'pass12345'}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


@pytest.fixture
def w(db):
    from core.feedtypes import ensure_defaults
    ensure_defaults()
    farm = Farm.objects.create(farm_code='A1', name='Lakshmi', owner_name='o', region='Zone-A', capacity=5000)
    fl = Flock.objects.create(farm=farm, placement_date=T - datetime.timedelta(days=30), chick_count=1000)
    return {'farm': farm, 'flock': fl, 'admin': login('boss', 'admin'), 'sup': login('ravi', 'supervisor'),
            'mill': login('mill', 'plant')}


def test_everyone_reads_the_list_only_admin_changes_it(w):
    for who in ('admin', 'sup', 'mill'):
        rows = w[who].get('/api/feed-types/').data
        assert [r['code'] for r in rows] == ['BPSC', 'BSC', 'BFP']
    assert w['sup'].post('/api/feed-types/', {'code': 'X'}, format='json').status_code == 403
    assert w['mill'].patch(f"/api/feed-types/{FeedType.objects.get(key='BFP').id}/", {'code': 'Y'},
                           format='json').status_code == 403


def test_rename_bfp_to_bfp1_and_add_bfp2(w):
    fl, admin = w['flock'], w['admin']
    FeedOrder.objects.create(farm=w['farm'], flock=fl, feed_type='BFP', quantity_bags=50, status='delivered')
    DailyEntry.objects.create(flock=fl, date=T - datetime.timedelta(days=2), feed_bags={'BFP': 10})
    bfp = FeedType.objects.get(key='BFP')
    r = admin.patch(f'/api/feed-types/{bfp.id}/', {'code': 'bfp1', 'name': 'Finisher 1', 'per_bird_kg': '1.5'},
                    format='json')
    assert r.status_code == 200 and r.data['code'] == 'BFP1' and r.data['key'] == 'BFP'
    r = admin.post('/api/feed-types/', {'code': 'BFP2', 'name': 'Finisher 2', 'colour': '#7C2D12'}, format='json')
    assert r.status_code == 201 and r.data['key'] == 'BFP2' and r.data['sort_order'] == 4
    # history kept: the old BFP bags are now shown as BFP1
    cum = admin.get(f'/api/flocks/{fl.id}/cumulative/').data
    assert cum['feed_by_type'] == {'BFP': {'bags': 10, 'kg': 500}}
    assert cum['flock_feed_stock']['by_type'] == {'BFP': 40}
    # the new type works everywhere: order it, feed it, count it
    assert w['sup'].post('/api/feed-orders/', {'farm': w['farm'].id, 'flock': fl.id, 'feed_type': 'BFP2',
                                               'quantity_bags': 20}, format='json').status_code == 201
    FeedOrder.objects.filter(feed_type='BFP2').update(status='delivered')
    r = w['sup'].post('/api/daily-entries/', {'flock': fl.id, 'date': str(T), 'feed_bags': {'BFP': 5, 'BFP2': 3}},
                      format='json')
    assert r.status_code == 201, r.data
    assert r.data['feed_bags'] == {'BFP': 5, 'BFP2': 3}
    stock = admin.get(f'/api/flocks/{fl.id}/cumulative/').data['flock_feed_stock']
    assert stock == {'by_type': {'BFP': 35, 'BFP2': 17}, 'total': 52}


def test_stock_check_names_the_feed_by_its_current_code(w):
    fl = w['flock']
    FeedType.objects.filter(key='BFP').update(code='BFP1')
    FeedOrder.objects.create(farm=w['farm'], flock=fl, feed_type='BFP', quantity_bags=4, status='delivered')
    r = w['sup'].post('/api/daily-entries/', {'flock': fl.id, 'date': str(T), 'feed_bags': {'BFP': 9}},
                      format='json')
    assert r.status_code == 400 and 'Only 4 BFP1 bags in stock' in str(r.data)
    r = w['sup'].post('/api/daily-entries/', {'flock': fl.id, 'date': str(T), 'feed_bags': {'NOPE': 1}},
                      format='json')
    assert r.status_code == 400 and 'Unknown feed type' in str(r.data)
    r = w['sup'].post('/api/daily-entries/', {'flock': fl.id, 'date': str(T), 'feed_bags': {'BFP': -1}},
                      format='json')
    assert r.status_code == 400


def test_retire_and_delete_rules(w):
    admin, fl = w['admin'], w['flock']
    bpsc = FeedType.objects.get(key='BPSC')
    FeedOrder.objects.create(farm=w['farm'], flock=fl, feed_type='BPSC', quantity_bags=5, status='delivered')
    r = admin.delete(f'/api/feed-types/{bpsc.id}/')
    assert r.status_code == 400 and 'Retire it instead' in str(r.data)
    assert admin.patch(f'/api/feed-types/{bpsc.id}/', {'active': False}, format='json').status_code == 200
    # retired: can't be chosen for new records …
    r = w['sup'].post('/api/feed-orders/', {'farm': w['farm'].id, 'flock': fl.id, 'feed_type': 'BPSC',
                                            'quantity_bags': 1}, format='json')
    assert r.status_code == 400 and 'retired' in str(r.data)
    # … but old records still show it
    assert admin.get(f'/api/flocks/{fl.id}/cumulative/').data['flock_feed_stock']['by_type'] == {'BPSC': 5}
    # an unused type can be deleted; the last active one can't be retired
    new = admin.post('/api/feed-types/', {'code': 'TEST'}, format='json').data
    assert admin.delete(f"/api/feed-types/{new['id']}/").status_code == 204
    FeedType.objects.filter(key='BSC').update(active=False)
    bfp = FeedType.objects.get(key='BFP')
    assert admin.patch(f'/api/feed-types/{bfp.id}/', {'active': False}, format='json').status_code == 400
    assert admin.post('/api/feed-types/', {'code': 'bad code!'}, format='json').status_code == 400


def test_current_feed_follows_the_per_bird_amounts(w):
    fl = w['flock']                      # 1000 chicks: BPSC 0.5 kg/bird = 10 bags, BSC 1.0 kg/bird = 20 bags
    s = lambda: w['admin'].get(f'/api/flocks/{fl.id}/cumulative/').data['feed_schedule_status']   # noqa: E731
    assert s()['current_feed_type'] == 'BPSC'
    DailyEntry.objects.create(flock=fl, date=T - datetime.timedelta(days=5), feed_bags={'BPSC': 10})
    assert s()['current_feed_type'] == 'BSC'
    DailyEntry.objects.create(flock=fl, date=T - datetime.timedelta(days=4), feed_bags={'BSC': 20})
    st = s()
    assert st['current_feed_type'] == 'BFP'
    row = {r['feed_type']: r for r in st['types']}
    assert row['BPSC']['estimate_bags'] == 10 and row['BPSC']['remaining_kg'] == 0
    assert row['BFP']['estimate_kg'] is None


@pytest.mark.django_db(transaction=True)
def test_migration_moves_real_old_data_into_feed_types():
    """Migrate a database with old-style rows (BPSC/BSC/BFP columns) forward and check
    every bag lands in the new per-type lines, then migrate back and check again."""
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    before, after = [('core', '0039_feed_types_add')], [('core', '0041_feed_types_remove_columns')]
    ex = MigrationExecutor(connection)
    ex.migrate(before)
    old = ex.loader.project_state(before).apps
    Farm_, Flock_ = old.get_model('core', 'Farm'), old.get_model('core', 'Flock')
    Entry_, Count_ = old.get_model('core', 'DailyEntry'), old.get_model('core', 'FeedStockCount')
    old.get_model('core', 'FeedType').objects.all().delete()
    farm = Farm_.objects.create(farm_code='M1', name='M', owner_name='o', region='Z', capacity=1)
    fl = Flock_.objects.create(farm=farm, placement_date=T - datetime.timedelta(days=20), chick_count=100,
                               bpsc_per_bird_kg=Decimal('0.6'), bsc_per_bird_kg=Decimal('1.1'))
    e1 = Entry_.objects.create(flock=fl, date=T - datetime.timedelta(days=5), feed_bpsc_bags=3, feed_bsc_bags=1)
    e2 = Entry_.objects.create(flock=fl, date=T - datetime.timedelta(days=4), feed_bfp_bags=7)
    c = Count_.objects.create(flock=fl, date=T, bpsc_bags=2, bfp_bags=4)

    ex = MigrationExecutor(connection)
    ex.loader.build_graph()
    ex.migrate(after)
    new = ex.loader.project_state(after).apps
    types = {t.key: t for t in new.get_model('core', 'FeedType').objects.all()}
    assert set(types) == {'BPSC', 'BSC', 'BFP'} and types['BPSC'].per_bird_kg == Decimal('0.6')
    assert types['BSC'].per_bird_kg == Decimal('1.1') and types['BFP'].per_bird_kg is None
    lines = {(x.entry_id, x.feed_type): x.bags for x in new.get_model('core', 'DailyEntryFeed').objects.all()}
    assert lines == {(e1.id, 'BPSC'): 3, (e1.id, 'BSC'): 1, (e2.id, 'BFP'): 7}
    assert new.get_model('core', 'FeedStockCount').objects.get(pk=c.pk).bags == {'BPSC': 2, 'BFP': 4}

    ex = MigrationExecutor(connection)
    ex.loader.build_graph()
    ex.migrate(before)                                     # and back again
    back = ex.loader.project_state(before).apps
    e = back.get_model('core', 'DailyEntry').objects.get(pk=e1.pk)
    assert (e.feed_bpsc_bags, e.feed_bsc_bags, e.feed_bfp_bags) == (3, 1, 0)
    assert back.get_model('core', 'FeedStockCount').objects.get(pk=c.pk).bfp_bags == 4
    ex = MigrationExecutor(connection)
    ex.loader.build_graph()
    ex.migrate(ex.loader.graph.leaf_nodes())               # leave the database as it was
