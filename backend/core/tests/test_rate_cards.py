"""Rate cards: several dated cards, two growing-charge methods, card chosen when billing,
bill preview, and the admin API."""
import datetime
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.billing import generate_bill, growing_charge_per_kg
from core.models import Bill, BillConfig, DailyEntry, Flock, Sale, UserProfile

pytestmark = pytest.mark.django_db
D = Decimal


def nov_2026_card(**kw):
    """The Jangaon card effective 1 Nov 2026."""
    values = dict(
        name='Nov 2026', effective_from=datetime.date(2026, 11, 1), growing_method='standard',
        feed_cost_per_kg=D('45.30'), chick_cost_per_bird=D('34'), admin_cost_per_chick=D('6'),
        medicine_always_actual=True, standard_fcr=D('1.60'), standard_avg_weight_kg=D('2.00'),
        standard_mortality_pct=D('5'), standard_production_cost=D('95'), standard_growing_charges=D('8.50'),
        min_growing_charges=D('5.50'), gc_increase_pct=D('50'), gc_decrease_pct=D('50'),
        incentive_threshold_1=D('110'), incentive_threshold_2=D('120'),
        incentive_rate_1=D('0.05'), incentive_rate_2=D('0.10'), max_rate_incentive=D('2.50'),
        is_active=False,
    )
    values.update(kw)
    return BillConfig.objects.create(**values)


def plain(farm):
    for f in ('recovery_excess_mortality', 'recovery_negligence', 'recovery_shortage', 'recovery_fcr', 'recovery_ifft'):
        setattr(farm, f, False)
    farm.save()
    return farm


def sold_flock(farm, placed, rate='125', status='closed'):
    """1000 chicks, 60 bags (3000 kg) fed, all sold: 2000 kg at `rate`."""
    fl = Flock.objects.create(farm=farm, placement_date=placed, chick_count=1000, status=status)
    DailyEntry.objects.create(flock=fl, date=placed + datetime.timedelta(days=1), feed_bags={'BFP': 60})
    Sale.objects.create(flock=fl, date=placed + datetime.timedelta(days=40), bird_count=1000,
                        total_weight_kg=D('2000'), rate_per_kg=D(rate), trader_name='t')
    return fl


class TestStandardMethod:
    @pytest.mark.parametrize('cost, expected', [
        ('93', '9.50'),        # ₹2 below standard → +₹1.00
        ('95', '8.50'),
        ('98', '7.00'),        # ₹3 above → −₹1.50
        ('102', '5.50'),       # 8.50 − 3.50 = 5.00 → minimum 5.50
    ])
    def test_the_examples_on_the_card(self, cost, expected):
        card = nov_2026_card()
        assert growing_charge_per_kg(card, D('0'), D(cost), 'Z') == D(expected)

    def test_grade_does_not_matter_and_ceiling_applies(self):
        card = nov_2026_card(max_growing_charges=D('10'))
        assert growing_charge_per_kg(card, D('0'), D('93'), 'A+') == growing_charge_per_kg(card, D('0'), D('93'), 'Z')
        assert growing_charge_per_kg(card, D('0'), D('80'), 'A+') == D('10')        # 16.00 → ceiling 10

    def test_different_up_and_down_rates(self):
        card = nov_2026_card(gc_increase_pct=D('40'), gc_decrease_pct=D('60'))
        assert growing_charge_per_kg(card, D('0'), D('93'), 'A') == D('9.30')
        assert growing_charge_per_kg(card, D('0'), D('97'), 'A') == D('7.30')

    def test_full_bill(self, farm):
        plain(farm)
        card = nov_2026_card(medicine_always_actual=False, medicine_cost_per_chick=D('0'))
        fl = sold_flock(farm, datetime.date(2026, 11, 2))
        bill = generate_bill(fl, config=card)
        # cost: chicks 34,000 + feed 3,000 kg × 45.30 = 1,35,900 + admin 6,000 = 1,75,900 / 2,000 kg = 87.95
        assert bill.production_cost_per_kg == D('87.95')
        # 8.50 + (95 − 87.95) × 50% = 12.025 → 12.03
        assert bill.growing_charges_per_kg == D('12.03')
        assert bill.growing_charges_total == D('24060.00')
        # sold at 125: (120 − 110) × 0.05 + (125 − 120) × 0.10 = 1.00
        assert bill.rate_incentive_per_kg == D('1.00')
        assert bill.rate_card == card
        assert bill.config_snapshot['rate_card_name'] == 'Nov 2026'
        assert bill.config_snapshot['growing_method'] == 'standard'

    def test_medicine_at_actual_for_every_farm(self, farm):
        from core.models import Medication
        plain(farm)
        farm.medicine_use_actual = False
        farm.save()
        fl = sold_flock(farm, datetime.date(2026, 11, 2))
        Medication.objects.create(flock=fl, date=fl.placement_date, name='m', cost=D('1234'))
        assert generate_bill(fl, config=nov_2026_card()).medicine_cost == D('1234')


class TestWhichCard:
    def test_card_in_effect_on_the_placement_date(self, farm):
        old = BillConfig.get_active()                              # the original card, no date
        oct_card = nov_2026_card(name='Oct', effective_from=datetime.date(2026, 10, 1))
        nov = nov_2026_card()
        assert BillConfig.for_date(datetime.date(2026, 9, 30)) == old
        assert BillConfig.for_date(datetime.date(2026, 10, 31)) == oct_card
        assert BillConfig.for_date(datetime.date(2026, 11, 1)) == nov
        plain(farm)
        assert generate_bill(sold_flock(farm, datetime.date(2026, 10, 20))).rate_card == oct_card

    def test_old_method_still_works(self, farm):
        plain(farm)
        old = BillConfig.get_active()                              # margin & grade
        fl = sold_flock(farm, datetime.date(2026, 9, 1), rate='100')
        bill = generate_bill(fl, config=old)
        # defaults: cost (34,000 + 3,000 × 44 + 5,000 + 6,000) / 2,000 = 88.50 → grade A+
        # (100 − 88.50) × 1.5 = 17.25
        assert bill.production_cost_per_kg == D('88.50') and bill.farmer_grade == 'A+'
        assert bill.growing_charges_per_kg == D('17.25')


def login(username, role):
    u = User.objects.create_user(username=username, password='pass12345')
    UserProfile.objects.create(user=u, role=role, assigned_regions=['Zone-A'])
    u.profile.sync_farms_from_regions()
    c = APIClient()
    r = c.post('/api/auth/login/', {'username': username, 'password': 'pass12345'}, format='json')
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
    return c


class TestApi:
    def test_admin_manages_cards_others_cannot(self, farm):
        admin = login('boss', 'admin')
        sup = login('ravi', 'supervisor')
        assert sup.get('/api/rate-cards/').status_code == 403
        assert sup.post('/api/rate-cards/', {'name': 'x'}, format='json').status_code == 403
        cards = admin.get('/api/rate-cards/').data
        assert len(cards) == 1 and cards[0]['is_active']
        r = admin.post('/api/rate-cards/', {'name': 'Nov 2026', 'effective_from': '2026-11-01',
                                             'growing_method': 'standard', 'feed_cost_per_kg': '45.30',
                                             'standard_growing_charges': '8.50'}, format='json')
        assert r.status_code == 201, r.data
        new = r.data
        assert new['chick_cost_per_bird'] == cards[0]['chick_cost_per_bird']     # copied
        assert new['feed_cost_per_kg'] == '45.30' and not new['is_active']
        assert admin.patch(f"/api/rate-cards/{new['id']}/", {'min_growing_charges': '5.50'},
                           format='json').data['min_growing_charges'] == '5.50'
        # default card can't be deleted; make the new one default
        assert admin.delete(f"/api/rate-cards/{cards[0]['id']}/").status_code == 400
        assert admin.post(f"/api/rate-cards/{new['id']}/make-default/").data['is_active']
        assert BillConfig.objects.filter(is_active=True).count() == 1
        assert admin.delete(f"/api/rate-cards/{cards[0]['id']}/").status_code == 204

    def test_a_card_used_for_a_bill_is_kept(self, farm):
        admin = login('boss', 'admin')
        plain(farm)
        card = nov_2026_card()
        generate_bill(sold_flock(farm, datetime.date(2026, 11, 2)), config=card)
        r = admin.delete(f'/api/rate-cards/{card.id}/')
        assert r.status_code == 400 and 'kept for the record' in r.data['error']
        assert admin.get(f'/api/rate-cards/{card.id}/').data['bills_count'] == 1

    def test_admin_picks_the_card_when_closing(self, farm):
        admin = login('boss', 'admin')
        plain(farm)
        BillConfig.get_active()
        nov = nov_2026_card()
        old = BillConfig.objects.get(is_active=True)
        fl = sold_flock(farm, datetime.date(2026, 11, 2), status='active')
        # preview: suggested card is the one for the placement date; nothing saved
        p = admin.post(f'/api/flocks/{fl.id}/bill-preview/', {'recovery_ifft': True}, format='json').data
        assert p['suggested_card'] == nov.id and p['rate_card'] == nov.id and p['suggested_card_name'] == 'Nov 2026'
        p_old = admin.post(f'/api/flocks/{fl.id}/bill-preview/', {'rate_card': old.id}, format='json').data
        assert p_old['rate_card_name'] == old.label and p_old['growing_method'] == 'margin_grade'
        fl.refresh_from_db()
        farm.refresh_from_db()
        assert fl.status == 'active' and not Bill.objects.exists() and farm.recovery_ifft is False
        r = admin.post(f'/api/flocks/{fl.id}/close-and-bill/', {'rate_card': old.id}, format='json')
        assert r.status_code == 201
        assert r.data['rate_card'] == old.id and r.data['rate_card_name'] == old.label
        assert r.data['net_payable'] == p_old['net_payable']

    def test_supervisor_gets_the_card_for_the_placement_date(self, farm):
        sup = login('ravi', 'supervisor')
        plain(farm)
        old = BillConfig.get_active()
        nov = nov_2026_card()
        fl = sold_flock(farm, datetime.date(2026, 11, 2), status='active')
        assert sup.post(f'/api/flocks/{fl.id}/bill-preview/', {}, format='json').status_code == 403
        r = sup.post(f'/api/flocks/{fl.id}/close-and-bill/', {'rate_card': old.id}, format='json')
        assert r.status_code == 201
        assert r.data['rate_card'] == nov.id and r.data['rate_card_name'] == 'Nov 2026'
        assert 'config_snapshot' not in r.data                     # costs stay hidden
