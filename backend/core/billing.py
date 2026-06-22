from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum, Avg
from .models import (
    Flock, DailyEntry, Sale, FeedOrder, BillConfig, Bill, Farm
)


def generate_bill(flock, user=None):
    """Generate a bill for a closed flock."""
    config = BillConfig.get_active()
    farm = flock.farm
    BAG_KG = 50

    # ─── FLOCK DATA ───
    chicks_placed = flock.chick_count
    entries = DailyEntry.objects.filter(flock=flock).order_by('date')
    sales = Sale.objects.filter(flock=flock)

    total_mortality = entries.aggregate(t=Sum('mortality_count'))['t'] or 0
    total_sold_birds = sales.aggregate(t=Sum('bird_count'))['t'] or 0
    total_sold_weight = Decimal(str(sales.aggregate(t=Sum('total_weight_kg'))['t'] or 0))
    live_birds = chicks_placed - total_mortality - total_sold_birds

    # Average selling price
    total_sale_amount = Decimal('0')
    for s in sales.filter(rate_per_kg__isnull=False):
        total_sale_amount += s.total_weight_kg * s.rate_per_kg
    avg_selling_price = (total_sale_amount / total_sold_weight) if total_sold_weight > 0 else Decimal('0')

    # Feed
    feed_agg = entries.aggregate(
        bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'),
    )
    total_feed_bags = Decimal(str(
        (feed_agg['bpsc'] or 0) + (feed_agg['bsc'] or 0) + (feed_agg['bfp'] or 0)
    ))
    total_feed_kg = total_feed_bags * BAG_KG

    # ─── COST CALCULATION ───
    chick_cost = Decimal(str(chicks_placed)) * config.chick_cost_per_bird
    feed_cost = total_feed_kg * config.feed_cost_per_kg

    # Medicine cost: actual if flag is on, else chicks × rate
    if farm.medicine_use_actual:
        medicine_cost = Decimal(str(flock.total_medication_cost))
    else:
        medicine_cost = Decimal(str(chicks_placed)) * config.medicine_cost_per_chick
    # Admin cost = per live chick (sold + remaining live)
    admin_birds = total_sold_birds + max(0, live_birds)
    admin_cost = Decimal(str(admin_birds)) * config.admin_cost_per_chick

    production_cost_total = chick_cost + feed_cost + medicine_cost + admin_cost
    production_cost_per_kg = (production_cost_total / total_sold_weight) if total_sold_weight > 0 else Decimal('0')
    production_cost_per_kg = production_cost_per_kg.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # ─── FARMER GRADE ───
    if production_cost_per_kg <= config.grade_a_plus_max:
        grade = 'A+'
    elif production_cost_per_kg <= config.grade_a_max:
        grade = 'A'
    elif production_cost_per_kg <= config.grade_b_max:
        grade = 'B'
    elif production_cost_per_kg <= config.grade_c_max:
        grade = 'C'
    elif production_cost_per_kg <= config.grade_d_max:
        grade = 'D'
    else:
        grade = 'Z'

    # ─── GROWING CHARGES ───
    growing_charges_per_kg = avg_selling_price - production_cost_per_kg
    # Apply min
    growing_charges_per_kg = max(growing_charges_per_kg, config.min_growing_charges)

    # Grade adjustment (50% incentive/penalty)
    grade_factor = config.grade_incentive_pct / Decimal('100')
    if grade in ('A+', 'A'):
        growing_charges_per_kg = growing_charges_per_kg * (1 + grade_factor)
    elif grade in ('B', 'C', 'D', 'Z'):
        growing_charges_per_kg = growing_charges_per_kg * (1 - grade_factor)

    growing_charges_per_kg = growing_charges_per_kg.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    growing_charges_total = (growing_charges_per_kg * total_sold_weight).quantize(Decimal('0.01'))

    # ─── RATE INCENTIVE ───
    rate_incentive_per_kg = Decimal('0')
    if avg_selling_price > config.incentive_threshold_2:
        rupees_above = avg_selling_price - config.incentive_threshold_1
        rupees_tier1 = config.incentive_threshold_2 - config.incentive_threshold_1
        rupees_tier2 = avg_selling_price - config.incentive_threshold_2
        rate_incentive_per_kg = (rupees_tier1 * config.incentive_rate_1) + (rupees_tier2 * config.incentive_rate_2)
    elif avg_selling_price > config.incentive_threshold_1:
        rupees_above = avg_selling_price - config.incentive_threshold_1
        rate_incentive_per_kg = rupees_above * config.incentive_rate_1

    rate_incentive_per_kg = min(rate_incentive_per_kg, config.max_rate_incentive)
    rate_incentive_per_kg = rate_incentive_per_kg.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    rate_incentive_total = (rate_incentive_per_kg * total_sold_weight).quantize(Decimal('0.01'))

    # ─── RECOVERIES ───
    first_week_recovery = Decimal('0')
    negligence_recovery = Decimal('0')
    shortage_recovery = Decimal('0')
    fcr_recovery = Decimal('0')
    ifft_charges = Decimal('0')

    # 1. First week excess mortality
    if farm.recovery_excess_mortality:
        first_week_entries = entries.filter(
            date__lte=flock.placement_date + __import__('datetime').timedelta(days=7)
        )
        first_week_deaths = first_week_entries.aggregate(t=Sum('mortality_count'))['t'] or 0
        first_week_pct = (first_week_deaths / chicks_placed) * 100 if chicks_placed > 0 else 0
        if first_week_pct > float(config.first_week_mortality_limit_pct):
            excess_chicks = first_week_deaths - int(chicks_placed * float(config.first_week_mortality_limit_pct) / 100)
            if excess_chicks > 0:
                first_week_recovery = Decimal(str(excess_chicks)) * config.first_week_recovery_per_chick

    # 2. Farmer negligence (flag-based, manual — just record if flagged)
    if farm.recovery_negligence:
        # Calculate based on mortality by age bracket
        for entry in entries:
            if entry.mortality_count > 0:
                day = (entry.date - flock.placement_date).days
                if day <= 15:
                    negligence_recovery += Decimal(str(entry.mortality_count)) * config.negligence_rate_1_15
                elif day <= 20:
                    negligence_recovery += Decimal(str(entry.mortality_count)) * config.negligence_rate_16_20
                elif day <= 35:
                    negligence_recovery += Decimal(str(entry.mortality_count)) * config.negligence_rate_21_35
                else:
                    negligence_recovery += Decimal(str(entry.mortality_count)) * config.negligence_rate_above_35

    # 3. Shortage of birds
    if farm.recovery_shortage:
        expected_live = chicks_placed - total_mortality
        actual_accounted = total_sold_birds + max(0, live_birds)
        shortage = expected_live - actual_accounted
        if shortage > 0:
            # Avg body weight
            avg_wt = (total_sold_weight / Decimal(str(total_sold_birds))) if total_sold_birds > 0 else Decimal('2')
            shortage_weight = Decimal(str(shortage)) * avg_wt
            # Recovery at higher of market rate or production cost
            market_rate = avg_selling_price
            recovery_rate = max(market_rate, production_cost_per_kg)
            shortage_recovery = (shortage_weight * recovery_rate).quantize(Decimal('0.01'))

    # 4. FCR recovery
    if farm.recovery_fcr and total_sold_weight > 0:
        actual_fcr = float(total_feed_kg) / float(total_sold_weight)
        # Get area/region average FCR
        region_flocks = Flock.objects.filter(
            farm__region=farm.region, status='closed'
        ).exclude(id=flock.id)
        if region_flocks.exists():
            region_feed = Decimal('0')
            region_sold = Decimal('0')
            for rf in region_flocks:
                rf_feed_agg = DailyEntry.objects.filter(flock=rf).aggregate(
                    bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'),
                )
                rf_feed = ((rf_feed_agg['bpsc'] or 0) + (rf_feed_agg['bsc'] or 0) + (rf_feed_agg['bfp'] or 0)) * BAG_KG
                rf_sold = Sale.objects.filter(flock=rf).aggregate(t=Sum('total_weight_kg'))['t'] or 0
                region_feed += Decimal(str(rf_feed))
                region_sold += Decimal(str(rf_sold))
            if region_sold > 0:
                region_avg_fcr = float(region_feed) / float(region_sold)
                if actual_fcr > region_avg_fcr:
                    excess_feed_kg = total_feed_kg - (Decimal(str(region_avg_fcr)) * total_sold_weight)
                    if excess_feed_kg > 0:
                        fcr_recovery = (excess_feed_kg * config.feed_cost_per_kg).quantize(Decimal('0.01'))

    # 5. IFFT charges
    if farm.recovery_ifft:
        ifft_charges = (total_feed_bags * config.ifft_per_bag).quantize(Decimal('0.01'))

    total_recoveries = (first_week_recovery + negligence_recovery + shortage_recovery + fcr_recovery + ifft_charges).quantize(Decimal('0.01'))

    # ─── FINAL ───
    gross_payable = growing_charges_total + rate_incentive_total
    net_payable = (gross_payable - total_recoveries).quantize(Decimal('0.01'))

    # ─── SAVE ───
    bill = Bill.objects.create(
        flock=flock,
        generated_by=user,
        chicks_placed=chicks_placed,
        total_mortality=total_mortality,
        live_birds=max(0, live_birds),
        total_sold_birds=total_sold_birds,
        total_sold_weight_kg=total_sold_weight,
        avg_selling_price=avg_selling_price.quantize(Decimal('0.01')),
        age_days=flock.age_days,
        total_feed_kg=total_feed_kg,
        total_feed_bags=total_feed_bags,
        chick_cost=chick_cost,
        feed_cost=feed_cost,
        medicine_cost=medicine_cost,
        admin_cost=admin_cost,
        production_cost_total=production_cost_total.quantize(Decimal('0.01')),
        production_cost_per_kg=production_cost_per_kg,
        farmer_grade=grade,
        growing_charges_per_kg=growing_charges_per_kg,
        growing_charges_total=growing_charges_total,
        rate_incentive_per_kg=rate_incentive_per_kg,
        rate_incentive_total=rate_incentive_total,
        first_week_mortality_recovery=first_week_recovery,
        negligence_recovery=negligence_recovery,
        shortage_recovery=shortage_recovery,
        fcr_recovery=fcr_recovery,
        ifft_charges=ifft_charges,
        total_recoveries=total_recoveries,
        gross_payable=gross_payable.quantize(Decimal('0.01')),
        net_payable=net_payable,
        config_snapshot={
            'chick_cost_per_bird': str(config.chick_cost_per_bird),
            'feed_cost_per_kg': str(config.feed_cost_per_kg),
            'admin_cost_per_chick': str(config.admin_cost_per_chick),
            'medicine_cost_per_chick': str(config.medicine_cost_per_chick),
            'medicine_use_actual': farm.medicine_use_actual,
        },
    )
    return bill
