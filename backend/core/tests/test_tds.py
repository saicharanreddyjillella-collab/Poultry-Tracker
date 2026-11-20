"""TDS on grower payments (Section 194C) — 2.1/2.2."""
import datetime
from decimal import Decimal, ROUND_HALF_UP

import pytest

from core.models import DailyEntry, Sale, Farm
from core.billing import generate_bill

pytestmark = pytest.mark.django_db


def _entry(flock, day, mortality=0, bfp=0):
    return DailyEntry.objects.create(
        flock=flock, date=flock.placement_date + datetime.timedelta(days=day),
        mortality_count=mortality, feed_bags={'BFP': bfp},
    )


def _plain_farm(farm):
    farm.recovery_excess_mortality = False
    farm.recovery_negligence = False
    farm.recovery_shortage = False
    farm.recovery_fcr = False
    farm.recovery_ifft = False
    farm.save()
    return farm


def _bill_for(farm, make_flock):
    f = make_flock(farm, chicks=1000)
    _entry(f, 1, bfp=40)
    Sale.objects.create(flock=f, date=f.placement_date, bird_count=1000,
                        total_weight_kg=Decimal("2000"), rate_per_kg=Decimal("100"))
    return generate_bill(f)


class TestEntityTypeAndPan:
    def test_individual_rate_1pct(self, farm):
        farm.entity_type = "individual"; farm.save()
        assert farm.tds_rate_pct == Decimal("1")
        assert farm.is_individual_huf is True

    def test_company_rate_2pct(self, farm):
        farm.entity_type = "company"; farm.save()
        assert farm.tds_rate_pct == Decimal("2")
        assert farm.is_individual_huf is False

    def test_fpo_rate_2pct(self, farm):
        farm.entity_type = "fpo"; farm.save()
        assert farm.tds_rate_pct == Decimal("2")

    def test_pan_validation(self, farm):
        farm.pan = "ABCDE1234F"; farm.save()
        assert farm.has_valid_pan is True
        farm.pan = "BADPAN"; farm.save()
        assert farm.has_valid_pan is False
        farm.pan = ""; farm.save()
        assert farm.has_valid_pan is False

    def test_pan_rejected_by_api(self, auth_admin, farm):
        resp = auth_admin.patch(f"/api/farms/{farm.id}/", {"pan": "NOTVALID"}, format="json")
        assert resp.status_code >= 400
        ok = auth_admin.patch(f"/api/farms/{farm.id}/", {"pan": "abcde1234f"}, format="json")
        assert ok.status_code in (200, 202)
        farm.refresh_from_db()
        assert farm.pan == "ABCDE1234F"  # normalised to upper


class TestTdsComputation:
    def test_tds_on_net_payable_individual(self, farm, make_flock, config):
        _plain_farm(farm)
        farm.entity_type = "individual"; farm.pan = "ABCDE1234F"
        # disable thresholds so TDS always applies for this test
        config.apply_tds_thresholds = False; config.save()
        farm.save()
        bill = _bill_for(farm, make_flock)
        expected = (bill.net_payable * Decimal("1") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert bill.tds_rate_pct == Decimal("1")
        assert bill.tds_amount == expected
        assert bill.amount_paid == (bill.net_payable - expected).quantize(Decimal("0.01"))
        assert bill.tds_pan_missing is False

    def test_tds_company_is_2pct(self, farm, make_flock, config):
        _plain_farm(farm)
        farm.entity_type = "company"; farm.pan = "ABCDE1234F"
        config.apply_tds_thresholds = False; config.save()
        farm.save()
        bill = _bill_for(farm, make_flock)
        assert bill.tds_rate_pct == Decimal("2")
        expected = (bill.net_payable * Decimal("2") / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert bill.tds_amount == expected

    def test_pan_missing_flagged_rate_unchanged(self, farm, make_flock, config):
        _plain_farm(farm)
        farm.entity_type = "individual"; farm.pan = ""  # no PAN
        config.apply_tds_thresholds = False; config.save()
        farm.save()
        bill = _bill_for(farm, make_flock)
        # rate stays 1% (not bumped to 20%); only flagged
        assert bill.tds_rate_pct == Decimal("1")
        assert bill.tds_pan_missing is True

    def test_apply_tds_flag_off_means_no_tds(self, farm, make_flock, config):
        _plain_farm(farm)
        config.apply_tds = False; config.save()
        bill = _bill_for(farm, make_flock)
        assert bill.tds_amount == Decimal("0")
        assert bill.amount_paid == bill.net_payable


class TestThresholds:
    def test_below_single_limit_no_tds(self, farm, make_flock, config):
        """Small net payable under 30k + no prior FY bills -> no TDS."""
        _plain_farm(farm)
        config.apply_tds = True; config.apply_tds_thresholds = True; config.save()
        # tiny flock -> small net payable
        f = make_flock(farm, chicks=50)
        _entry(f, 1, bfp=2)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=50,
                            total_weight_kg=Decimal("100"), rate_per_kg=Decimal("100"))
        bill = generate_bill(f)
        if bill.net_payable <= config.tds_single_payment_limit:
            assert bill.tds_amount == Decimal("0")

    def test_above_single_limit_tds_applies(self, farm, make_flock, config):
        _plain_farm(farm)
        config.apply_tds = True; config.apply_tds_thresholds = True; config.save()
        farm.entity_type = "individual"; farm.save()
        # big flock -> net payable above 30k
        f = make_flock(farm, chicks=5000)
        _entry(f, 1, bfp=200)
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=5000,
                            total_weight_kg=Decimal("10000"), rate_per_kg=Decimal("120"))
        bill = generate_bill(f)
        if bill.net_payable > config.tds_single_payment_limit:
            assert bill.tds_amount > 0
