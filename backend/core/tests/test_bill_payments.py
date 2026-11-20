"""Bill approval and payments: a supervisor's bill waits for an admin; payments (part or
full) are recorded against the approved bill and survive a reopen."""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import Bill, BillPayment, DailyEntry, Farm, Flock, Sale, UserProfile

pytestmark = pytest.mark.django_db
T = datetime.date.today()
D = Decimal


def login(username, role):
    u = User.objects.create_user(username=username, password='pass12345')
    UserProfile.objects.create(user=u, role=role, assigned_regions=['Zone-A'])
    c = APIClient()
    r = c.post('/api/auth/login/', {'username': username, 'password': 'pass12345'}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


@pytest.fixture
def w(db):
    farm = Farm.objects.create(farm_code='A1', name='Lakshmi', owner_name='o', region='Zone-A', capacity=5000,
                               pan='ABCDE1234F')
    fl = Flock.objects.create(farm=farm, placement_date=T - datetime.timedelta(days=42), chick_count=1000)
    DailyEntry.objects.create(flock=fl, date=fl.placement_date + datetime.timedelta(days=1), feed_bfp_bags=60)
    Sale.objects.create(flock=fl, date=T, bird_count=1000, total_weight_kg=D('2000'), rate_per_kg=D('110'),
                        trader_name='t')
    return {'flock': fl, 'sup': login('ravi', 'supervisor'), 'admin': login('boss', 'admin')}


def close(c, fl):
    r = c.post(f'/api/flocks/{fl.id}/close-and-bill/', {}, format='json')
    assert r.status_code == 201, r.data
    return r.data


def test_supervisors_bill_waits_admins_is_approved(w):
    b = close(w['sup'], w['flock'])
    assert b['approval_status'] == 'pending' and b['approved_by_name'] is None
    assert w['sup'].post(f"/api/flocks/{w['flock'].id}/bill/approve/").status_code == 403
    r = w['admin'].post(f"/api/flocks/{w['flock'].id}/bill/approve/", {'note': 'checked'}, format='json')
    assert r.status_code == 200 and r.data['approval_status'] == 'approved' and r.data['approved_by_name'] == 'boss'
    assert w['admin'].post(f"/api/flocks/{w['flock'].id}/bill/approve/").status_code == 400
    assert [x['flock'] for x in w['admin'].get('/api/bills/?approval=approved').data] == [w['flock'].id]


def test_admins_own_bill_is_approved_at_once(w):
    assert close(w['admin'], w['flock'])['approval_status'] == 'approved'


def test_part_payments_and_balance(w):
    fl = w['flock']
    b = close(w['sup'], fl)
    due = D(b['amount_paid'])
    pay = lambda amt, **kw: w['admin'].post(f'/api/flocks/{fl.id}/bill/payments/',                  # noqa: E731
                                            {'date': str(T), 'amount': str(amt), 'mode': 'bank',
                                             'reference': 'UTR1', **kw}, format='json')
    assert pay(1000).status_code == 400                                # not approved yet
    w['admin'].post(f'/api/flocks/{fl.id}/bill/approve/')
    assert w['sup'].post(f'/api/flocks/{fl.id}/bill/payments/', {'date': str(T), 'amount': '1'},
                         format='json').status_code == 403
    r = pay(1000)
    assert r.status_code == 201, r.data
    assert r.data['payment_status'] == 'part' and D(r.data['balance_due']) == due - 1000
    assert r.data['payments'][0]['mode_label'] == 'Bank transfer' and r.data['payments'][0]['recorded_by_name'] == 'boss'
    assert pay(due).status_code == 400                                 # more than is due
    assert pay(0).status_code == 400
    assert pay(1, date=str(T - datetime.timedelta(days=400))).status_code == 400
    r = pay(due - 1000, mode='upi')
    assert r.data['payment_status'] == 'paid' and D(r.data['balance_due']) == 0
    assert len(w['admin'].get('/api/bills/?payment=paid').data) == 1
    # a mistaken payment can be removed by an admin
    pid = r.data['payments'][-1]['id']
    assert w['sup'].delete(f'/api/bill-payments/{pid}/').status_code == 403
    r = w['admin'].delete(f'/api/bill-payments/{pid}/')
    assert r.status_code == 200 and r.data['payment_status'] == 'part'


def test_payments_count_against_the_rebill_after_a_reopen(w):
    fl = w['flock']
    close(w['admin'], fl)
    w['admin'].post(f'/api/flocks/{fl.id}/bill/payments/', {'date': str(T), 'amount': '5000', 'mode': 'cash'},
                    format='json')
    r = w['admin'].post(f'/api/flocks/{fl.id}/reopen-bill/', {'reason': 'Sale weight corrected by trader'},
                        format='json')
    assert r.status_code == 200
    assert BillPayment.objects.filter(flock=fl).count() == 1           # kept
    b = close(w['admin'], fl)
    assert b['version'] == 2 and D(b['paid_total']) == D('5000')
    assert D(b['balance_due']) == D(b['amount_paid']) - 5000


def test_payment_date_is_checked_against_the_bills_indian_date(w):
    """BUG-029: a bill made just after midnight IST is still the previous day in UTC."""
    from django.utils import timezone
    fl = w['flock']
    close(w['admin'], fl)
    bill = Bill.objects.get(flock=fl)
    ist_midnight_plus = timezone.make_aware(datetime.datetime.combine(T, datetime.time(0, 10)))
    Bill.objects.filter(pk=bill.pk).update(generated_at=ist_midnight_plus)       # 18:40 UTC the day before
    r = w['admin'].post(f'/api/flocks/{fl.id}/bill/payments/',
                        {'date': str(T - datetime.timedelta(days=1)), 'amount': '1', 'mode': 'cash'}, format='json')
    assert r.status_code == 400 and 'date' in r.data
