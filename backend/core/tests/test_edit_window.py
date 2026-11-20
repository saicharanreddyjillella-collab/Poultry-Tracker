"""Edit window: supervisors change recent records themselves; older ones need an admin's approval."""
import datetime

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import AppSetting, ChangeRequest, DailyEntry, Farm, Flock, Medication, Sale, UserProfile

pytestmark = pytest.mark.django_db
T = datetime.date.today()
D = lambda n: str(T - datetime.timedelta(days=n))       # noqa: E731


def login(username, role, first=''):
    u = User.objects.create_user(username=username, password='pass12345', first_name=first)
    UserProfile.objects.create(user=u, role=role, assigned_regions=['Zone-A'])
    c = APIClient()
    r = c.post('/api/auth/login/', {'username': username, 'password': 'pass12345'}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


@pytest.fixture
def w(db):
    farm = Farm.objects.create(farm_code='A1', name='Lakshmi', owner_name='o', region='Zone-A', capacity=5000)
    fl = Flock.objects.create(farm=farm, placement_date=T - datetime.timedelta(days=30), chick_count=1000)
    old = DailyEntry.objects.create(flock=fl, date=T - datetime.timedelta(days=10), mortality_count=5)
    return {'flock': fl, 'old': old, 'sup': login('ravi', 'supervisor', 'Ravi'), 'admin': login('boss', 'admin')}


def entry(w, days_ago, **kw):
    return {'flock': w['flock'].id, 'date': D(days_ago), 'mortality_count': 1, **kw}


def test_inside_the_window_saves_at_once(w):
    for n in (0, 1, 2):                                  # 3-day window: today and the 2 days before
        assert w['sup'].post('/api/daily-entries/', entry(w, n), format='json').status_code == 201


def test_outside_the_window_needs_a_reason_then_waits(w):
    r = w['sup'].post('/api/daily-entries/', entry(w, 3), format='json')
    assert r.status_code == 400 and 'change_reason' in r.data and 'edit window' in str(r.data['change_reason'])
    r = w['sup'].post('/api/daily-entries/', entry(w, 3, change_reason='Forgot to enter'), format='json')
    assert r.status_code == 202 and r.data['status'] == 'pending'
    assert not DailyEntry.objects.filter(date=D(3)).exists()               # nothing saved yet
    cr = ChangeRequest.objects.get()
    assert (cr.model, cr.action, cr.reason, str(cr.record_date)) == ('DailyEntry', 'create', 'Forgot to enter', D(3))


def test_mistakes_are_shown_before_asking(w):
    r = w['sup'].post('/api/daily-entries/', entry(w, 5, date=D(5), mortality_count=-1, change_reason='x'),
                      format='json')
    assert r.status_code == 400 and not ChangeRequest.objects.exists()


def test_admin_approves_and_it_is_saved_as_the_supervisors(w):
    w['sup'].post('/api/daily-entries/', entry(w, 4, mortality_count=7, change_reason='Late'), format='json')
    cr = ChangeRequest.objects.get()
    assert w['sup'].post(f'/api/change-requests/{cr.id}/approve/').status_code == 403      # not their call
    r = w['admin'].post(f'/api/change-requests/{cr.id}/approve/', {'note': 'ok'}, format='json')
    assert r.status_code == 200 and r.data['status'] == 'approved' and r.data['decided_by_name'] == 'boss'
    e = DailyEntry.objects.get(date=D(4))
    assert e.mortality_count == 7 and e.entered_by.username == 'ravi'
    assert w['admin'].post(f'/api/change-requests/{cr.id}/approve/').status_code == 400      # only once


def test_change_and_delete_of_old_records(w):
    old = w['old']
    r = w['sup'].patch(f'/api/daily-entries/{old.id}/', {'mortality_count': 9, 'change_reason': 'Recount'},
                       format='json')
    assert r.status_code == 202
    old.refresh_from_db()
    assert old.mortality_count == 5                                        # unchanged until approved
    up = ChangeRequest.objects.get(action='update')
    assert up.before['mortality_count'] == 5 and up.payload == {'mortality_count': 9}
    w['admin'].post(f'/api/change-requests/{up.id}/approve/')
    old.refresh_from_db()
    assert old.mortality_count == 9 and old.edited_by.username == 'ravi'
    # moving a recent entry back into the past also needs approval
    recent = DailyEntry.objects.create(flock=w['flock'], date=T, mortality_count=0)
    assert w['sup'].patch(f'/api/daily-entries/{recent.id}/', {'date': D(8)}, format='json').status_code == 400
    # delete
    r = w['sup'].delete(f'/api/daily-entries/{old.id}/', {'change_reason': 'Duplicate'}, format='json')
    assert r.status_code == 202 and DailyEntry.objects.filter(pk=old.id).exists()
    dl = ChangeRequest.objects.get(action='delete')
    w['admin'].post(f'/api/change-requests/{dl.id}/reject/', {'note': 'Not a duplicate'}, format='json')
    assert DailyEntry.objects.filter(pk=old.id).exists()
    assert ChangeRequest.objects.get(pk=dl.id).status == 'rejected'


def test_sales_and_medicines_too(w):
    fl = w['flock']
    r = w['sup'].post('/api/sales/', {'flock': fl.id, 'date': D(6), 'bird_count': 10, 'total_weight_kg': '20',
                                      'trader_name': 't', 'change_reason': 'Late slip'}, format='json')
    assert r.status_code == 202
    r = w['sup'].post('/api/medications/', {'flock': fl.id, 'date': D(6), 'name': 'x', 'cost': '1',
                                            'change_reason': 'Late bill'}, format='json')
    assert r.status_code == 202
    for cr in ChangeRequest.objects.all():
        assert w['admin'].post(f'/api/change-requests/{cr.id}/approve/').status_code == 200
    assert Sale.objects.get().entered_by.username == 'ravi'
    assert Medication.objects.get().entered_by.username == 'ravi'


def test_approval_still_runs_the_normal_checks(w):
    fl = w['flock']
    w['sup'].post('/api/sales/', {'flock': fl.id, 'date': D(6), 'bird_count': 900, 'total_weight_kg': '20',
                                  'trader_name': 't', 'change_reason': 'Late'}, format='json')
    Sale.objects.create(flock=fl, date=T, bird_count=500, total_weight_kg=10, trader_name='t')   # birds gone since
    cr = ChangeRequest.objects.get()
    r = w['admin'].post(f'/api/change-requests/{cr.id}/approve/')
    assert r.status_code == 400 and 'bird_count' in str(r.data['detail'])
    assert ChangeRequest.objects.get().status == 'pending'


def test_admins_are_never_limited_and_the_window_is_a_setting(w):
    assert w['admin'].post('/api/daily-entries/', entry(w, 20), format='json').status_code == 201
    r = w['sup'].put('/api/settings/rules/', {'edit_window_days': 30}, format='json')
    assert r.status_code == 403
    r = w['admin'].put('/api/settings/rules/', {'edit_window_days': 15}, format='json')
    assert r.status_code == 200 and {x['key']: x['value'] for x in r.data}['edit_window_days'] == 15
    assert w['sup'].post('/api/daily-entries/', entry(w, 14), format='json').status_code == 201
    assert w['admin'].put('/api/settings/rules/', {'edit_window_days': 'x'}, format='json').status_code == 400
    AppSetting.objects.filter(key='edit_window_days').update(value=0)               # 0 = no limit
    assert w['sup'].post('/api/daily-entries/', entry(w, 25), format='json').status_code == 201


def test_supervisor_sees_requests_on_the_flock(w):
    w['sup'].post('/api/daily-entries/', entry(w, 4, change_reason='Late'), format='json')
    rows = w['sup'].get(f"/api/change-requests/?flock={w['flock'].id}&status=pending").data
    assert len(rows) == 1 and rows[0]['requested_by_name'] == 'Ravi' and rows[0]['action_label'] == 'Add'
