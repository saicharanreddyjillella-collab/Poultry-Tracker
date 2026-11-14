"""Bill engine tests — generate_bill() cost build-up, grading, incentives, recoveries.

Default BillConfig (model defaults) used throughout unless a test overrides it:
  chick 34, feed 44/kg, admin 6/chick, medicine 5/chick
  min_growing 4.50, grade A+ <=94, A <=95, B <=96, C <=97, D <=98 else Z
  grade_incentive 50%  | ifft 25/bag
  incentive thresholds 110/120, rates 0.05/0.10, max 2.50
"""
import datetime
from decimal import Decimal

import pytest

from core.models import DailyEntry, Sale, Medication, Flock, Bill
from core.billing import generate_bill

pytestmark = pytest.mark.django_db


def _entry(flock, day, mortality=0, bpsc=0, bsc=0, bfp=0):
    return DailyEntry.objects.create(
        flock=flock, date=flock.placement_date + datetime.timedelta(days=day),
        mortality_count=mortality, feed_bpsc_bags=bpsc, feed_bsc_bags=bsc, feed_bfp_bags=bfp,
    )


def _plain_farm(farm):
    """Turn OFF all recoveries so we can test the pure cost/charges path."""
    farm.recovery_excess_mortality = False
    farm.recovery_negligence = False
    farm.recovery_shortage = False
    farm.recovery_fcr = False
    farm.recovery_ifft = False
    farm.save()
    return farm


class TestCostBuildup:
    def test_basic_production_cost_per_kg(self, farm, make_flock, config):
        _plain_farm(farm)
        f = make_flock(farm, chicks=1000)
        # feed: 60 bags => 3000 kg
        _entry(f, 1, bfp=60)
        # no mortality, sell all as 2000 kg
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=1000,
                            total_weight_kg=Decimal("2000"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        # chick 1000*34=34000; feed 3000*44=132000; med 1000*5=5000
        # admin: sold 1000 + live 0 => 1000*6=6000
        assert bill.chick_cost == Decimal("34000")
        assert bill.feed_cost == Decimal("132000")
        assert bill.medicine_cost == Decimal("5000")
        assert bill.admin_cost == Decimal("6000")
        assert bill.production_cost_total == Decimal("177000")
        # /2000 sold kg = 88.50
        assert bill.production_cost_per_kg == Decimal("88.50")

    def test_medicine_actual_vs_flat(self, farm, make_flock, config):
        _plain_farm(farm)
        farm.medicine_use_actual = True
        farm.save()
        f = make_flock(farm, chicks=1000)
        _entry(f, 1, bfp=40)
        Medication.objects.create(flock=f, date=f.placement_date, name="X", cost=Decimal("777"))
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=1000,
                            total_weight_kg=Decimal("2000"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        assert bill.medicine_cost == Decimal("777")

    def test_avg_selling_price(self, farm, make_flock, config):
        _plain_farm(farm)
        f = make_flock(farm, chicks=1000)
        _entry(f, 1, bfp=40)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=500,
                            total_weight_kg=Decimal("1000"), rate_per_kg=Decimal("100"))
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=500,
                            total_weight_kg=Decimal("1000"), rate_per_kg=Decimal("120"))
        bill = generate_bill(f)
        # (1000*100 + 1000*120) / 2000 = 110
        assert bill.avg_selling_price == Decimal("110.00")


class TestGrading:
    @pytest.mark.parametrize("target_cost,weight,expected", [
        (Decimal("90.00"), Decimal("1477.78"), "A+"),   # <=94
        (Decimal("94.50"), Decimal("1407.41"), "A"),    # 94< x <=95
        (Decimal("95.50"), Decimal("1392.67"), "B"),    # 95< x <=96
        (Decimal("96.50"), Decimal("1378.24"), "C"),    # 96< x <=97
        (Decimal("97.50"), Decimal("1364.10"), "D"),    # 97< x <=98
        (Decimal("99.00"), Decimal("1343.43"), "Z"),    # above 98
    ])
    def test_grade_boundaries(self, farm, make_flock, config, target_cost, weight, expected):
        """Fix cost build-up (1000 chicks, 40 feed bags => total 133000) and tune the
        sold weight so production_cost_per_kg lands exactly on each grade band.
        total = chick 34000 + feed 40*50*44=88000 + med 5000 + admin 6000 = 133000.
        """
        _plain_farm(farm)
        f = make_flock(farm, chicks=1000)
        _entry(f, 1, bfp=40)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=1000,
                            total_weight_kg=weight, rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        assert bill.production_cost_total == Decimal("133000")
        assert bill.production_cost_per_kg == target_cost
        assert bill.farmer_grade == expected


class TestRecoveries:
    def test_ifft_charge_per_bag(self, farm, make_flock, config):
        _plain_farm(farm)
        farm.recovery_ifft = True
        farm.save()
        f = make_flock(farm, chicks=1000)
        _entry(f, 1, bfp=40)  # 40 bags
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=1000,
                            total_weight_kg=Decimal("2000"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        assert bill.ifft_charges == Decimal("1000.00")  # 40 * 25
        assert bill.total_recoveries == Decimal("1000.00")

    def test_first_week_excess_mortality_recovery(self, farm, make_flock, config):
        _plain_farm(farm)
        farm.recovery_excess_mortality = True
        farm.save()
        f = make_flock(farm, chicks=1000)
        # limit 1.5% of 1000 = 15 allowed. 40 deaths in week 1 => 25 excess.
        _entry(f, 2, mortality=40, bfp=40)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=900,
                            total_weight_kg=Decimal("1800"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        # 25 * 34 = 850
        assert bill.first_week_mortality_recovery == Decimal("850.00")

    def test_no_first_week_recovery_within_limit(self, farm, make_flock, config):
        _plain_farm(farm)
        farm.recovery_excess_mortality = True
        farm.save()
        f = make_flock(farm, chicks=1000)
        _entry(f, 2, mortality=10, bfp=40)  # 1% < 1.5% limit
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=990,
                            total_weight_kg=Decimal("1980"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        assert bill.first_week_mortality_recovery == Decimal("0")


class TestFinalPayable:
    def test_net_payable_is_gross_minus_recoveries(self, farm, make_flock, config):
        _plain_farm(farm)
        farm.recovery_ifft = True
        farm.save()
        f = make_flock(farm, chicks=1000)
        _entry(f, 1, bfp=40)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=1000,
                            total_weight_kg=Decimal("2000"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        expected = (bill.growing_charges_total + bill.rate_incentive_total) - bill.total_recoveries
        assert bill.net_payable == expected.quantize(Decimal("0.01"))

    def test_bill_is_persisted_one_per_flock(self, farm, make_flock, config):
        _plain_farm(farm)
        f = make_flock(farm, chicks=1000)
        _entry(f, 1, bfp=40)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=1000,
                            total_weight_kg=Decimal("2000"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        assert Bill.objects.filter(flock=f).count() == 1
        assert bill.config_snapshot["feed_cost_per_kg"] == "44.00"


class TestCullsAsMortality:
    """Business rule: culls are treated exactly as mortality in settlement."""

    def test_culls_reduce_live_birds_in_bill(self, farm, make_flock, config):
        _plain_farm(farm)
        f = make_flock(farm, chicks=1000)
        e = _entry(f, 1, mortality=30, bfp=40)
        e.cull_count = 20
        e.save()
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=900,
                            total_weight_kg=Decimal("1800"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        assert bill.total_mortality == 50
        assert bill.live_birds == 50

    def test_cull_equivalent_to_death_in_bill(self, farm, make_flock, config):
        _plain_farm(farm)
        a = make_flock(farm, chicks=1000)
        _entry(a, 1, mortality=40, bfp=40)
        Sale.objects.create(flock=a, date=a.placement_date, bird_count=900,
                            total_weight_kg=Decimal("1800"), rate_per_kg=Decimal("100"))
        bill_a = generate_bill(a)

        b = make_flock(farm, chicks=1000)
        eb = _entry(b, 1, mortality=20, bfp=40)
        eb.cull_count = 20
        eb.save()
        Sale.objects.create(flock=b, date=b.placement_date, bird_count=900,
                            total_weight_kg=Decimal("1800"), rate_per_kg=Decimal("100"))
        bill_b = generate_bill(b)

        assert bill_a.total_mortality == bill_b.total_mortality == 40
        assert bill_a.live_birds == bill_b.live_birds
        assert bill_a.admin_cost == bill_b.admin_cost
        assert bill_a.net_payable == bill_b.net_payable

    def test_first_week_recovery_counts_culls(self, farm, make_flock, config):
        farm.recovery_excess_mortality = True
        farm.recovery_negligence = False
        farm.recovery_shortage = False
        farm.recovery_fcr = False
        farm.recovery_ifft = False
        farm.save()
        f = make_flock(farm, chicks=1000)
        e = _entry(f, 2, mortality=10, bfp=40)
        e.cull_count = 30
        e.save()
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=900,
                            total_weight_kg=Decimal("1800"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        assert bill.first_week_mortality_recovery == Decimal("850.00")
