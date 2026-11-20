from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum, Avg
from django.utils import timezone
from .models import (
    Flock, DailyEntry, Sale, FeedOrder, BillConfig, Bill, Farm, BillVersion
)


def growing_charge_per_kg(config, avg_selling_price, production_cost_per_kg, grade):
    """₹/kg growing charge under the card's method (before rounding)."""
    if config.growing_method == BillConfig.METHOD_STANDARD:
        # Standard charge moves with the gap between standard and actual production cost:
        # each ₹1 below standard adds gc_increase_pct paise, each ₹1 above takes off gc_decrease_pct.
        gap = config.standard_production_cost - production_cost_per_kg
        pct = config.gc_increase_pct if gap >= 0 else config.gc_decrease_pct
        gc = config.standard_growing_charges + gap * pct / Decimal('100')
        if config.max_growing_charges is not None:
            gc = min(gc, config.max_growing_charges)
        return max(gc, config.min_growing_charges)
    # Margin & grade: selling price − production cost (at least the minimum), then ± % by grade.
    gc = max(avg_selling_price - production_cost_per_kg, config.min_growing_charges)
    grade_factor = config.grade_incentive_pct / Decimal('100')
    if grade in ('A+', 'A'):
        gc = gc * (1 + grade_factor)
    else:
        gc = gc * (1 - grade_factor)
    return gc


def generate_bill(flock, user=None, config=None):
    """Generate a bill for a closed flock with `config` (a rate card), or the card in
    effect on the flock's placement date."""
    config = config or BillConfig.for_date(flock.placement_date)
    config.refresh_from_db()  # Ensure all fields are Decimal, not float defaults
    farm = flock.farm
    BAG_KG = 50

    # ─── FLOCK DATA ───
    chicks_placed = flock.chick_count
    entries = DailyEntry.objects.filter(flock=flock).order_by('date')
    sales = Sale.objects.filter(flock=flock)

    # Culls are treated as mortality for settlement (per business rule).
    agg_losses = entries.aggregate(m=Sum('mortality_count'), c=Sum('cull_count'))
    total_mortality = (agg_losses['m'] or 0) + (agg_losses['c'] or 0)
    total_sold_birds = sales.aggregate(t=Sum('bird_count'))['t'] or 0
    total_sold_weight = Decimal(str(sales.aggregate(t=Sum('total_weight_kg'))['t'] or 0))
    live_birds = chicks_placed - total_mortality - total_sold_birds

    # Average selling price
    total_sale_amount = Decimal('0')
    for s in sales.filter(rate_per_kg__isnull=False):
        total_sale_amount += s.total_weight_kg * s.rate_per_kg
    avg_selling_price = (total_sale_amount / total_sold_weight) if total_sold_weight > 0 else Decimal('0')

    # Feed
    from .feedtypes import consumed_in, total
    total_feed_bags = Decimal(str(total(consumed_in(entries))))
    total_feed_kg = total_feed_bags * BAG_KG

    # ─── COST CALCULATION ───
    D = lambda v: Decimal(str(v))
    chick_cost = D(chicks_placed) * D(config.chick_cost_per_bird)
    feed_cost = D(total_feed_kg) * D(config.feed_cost_per_kg)

    # Medicine cost: actual if flag is on, else chicks × rate
    medicine_actual = farm.medicine_use_actual or config.medicine_always_actual
    if medicine_actual:
        medicine_cost = D(flock.total_medication_cost)
    else:
        medicine_cost = D(chicks_placed) * D(config.medicine_cost_per_chick)
    # Admin cost = per live chick (sold + remaining live)
    admin_birds = total_sold_birds + max(0, live_birds)
    admin_cost = D(admin_birds) * D(config.admin_cost_per_chick)

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

    # ─── GROWING CHARGES (method set on the rate card) ───
    growing_charges_per_kg = growing_charge_per_kg(config, avg_selling_price, production_cost_per_kg, grade)
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
        _fw = first_week_entries.aggregate(m=Sum('mortality_count'), c=Sum('cull_count'))
        first_week_deaths = (_fw['m'] or 0) + (_fw['c'] or 0)  # culls counted as mortality
        first_week_pct = (first_week_deaths / chicks_placed) * 100 if chicks_placed > 0 else 0
        if first_week_pct > float(config.first_week_mortality_limit_pct):
            excess_chicks = first_week_deaths - int(chicks_placed * float(config.first_week_mortality_limit_pct) / 100)
            if excess_chicks > 0:
                first_week_recovery = Decimal(str(excess_chicks)) * config.first_week_recovery_per_chick

    # 2. Farmer negligence (flag-based, manual — just record if flagged)
    if farm.recovery_negligence:
        # Calculate based on mortality by age bracket
        for entry in entries:
            entry_losses = entry.mortality_count + entry.cull_count  # culls counted as mortality
            if entry_losses > 0:
                day = (entry.date - flock.placement_date).days
                if day <= 15:
                    negligence_recovery += Decimal(str(entry_losses)) * config.negligence_rate_1_15
                elif day <= 20:
                    negligence_recovery += Decimal(str(entry_losses)) * config.negligence_rate_16_20
                elif day <= 35:
                    negligence_recovery += Decimal(str(entry_losses)) * config.negligence_rate_21_35
                else:
                    negligence_recovery += Decimal(str(entry_losses)) * config.negligence_rate_above_35

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
                rf_feed = total(consumed_in(DailyEntry.objects.filter(flock=rf))) * BAG_KG
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

    # ─── FCR BENCHMARK BAND (premium for beating, deduction for missing) ───
    # Independent of the area-average FCR recovery above; both are flag-gated
    # on the farm and can run together by explicit choice.
    fcr_benchmark_adjustment = Decimal('0')
    if farm.fcr_benchmark_enabled and total_sold_weight > 0:
        actual_fcr_b = Decimal(str(total_feed_kg)) / total_sold_weight
        benchmark = config.fcr_benchmark
        tol = benchmark * (config.fcr_benchmark_tolerance_pct / Decimal('100'))
        band_low = benchmark - tol
        band_high = benchmark + tol
        step = Decimal('0.1')
        if actual_fcr_b < band_low:
            # Beat the band -> premium. Steps measured from the lower edge.
            steps = (band_low - actual_fcr_b) / step
            per_kg = (steps * config.fcr_premium_per_kg_per_step)
            per_kg = min(per_kg, config.fcr_benchmark_max_adjustment_per_kg)
            fcr_benchmark_adjustment = (per_kg * total_sold_weight).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        elif actual_fcr_b > band_high:
            # Missed the band -> deduction (negative).
            steps = (actual_fcr_b - band_high) / step
            per_kg = (steps * config.fcr_deduction_per_kg_per_step)
            per_kg = min(per_kg, config.fcr_benchmark_max_adjustment_per_kg)
            fcr_benchmark_adjustment = -(per_kg * total_sold_weight).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # ─── FINAL ───
    gross_payable = growing_charges_total + rate_incentive_total + fcr_benchmark_adjustment
    net_payable = (gross_payable - total_recoveries).quantize(Decimal('0.01'))

    # ─── TDS (Section 194C) on the net amount payable to the grower ───
    # Base is the net payable (growing charges + incentive - recoveries) —
    # i.e. the grower's service income, excluding free-issued chicks/feed.
    tds_rate = Decimal('0')
    tds_amount = Decimal('0')
    pan_missing = not farm.has_valid_pan
    if config.apply_tds and net_payable > 0:
        apply = True
        if config.apply_tds_thresholds:
            # Indian financial year: Apr 1 - Mar 31.
            import datetime
            today = datetime.date.today()
            fy_start_year = today.year if today.month >= 4 else today.year - 1
            fy_start = datetime.date(fy_start_year, 4, 1)
            fy_end = datetime.date(fy_start_year + 1, 3, 31)
            prior = (Bill.objects
                     .filter(flock__farm=farm, generated_at__date__gte=fy_start,
                             generated_at__date__lte=fy_end)
                     .aggregate(t=Sum('net_payable'))['t'] or Decimal('0'))
            fy_aggregate = Decimal(str(prior)) + net_payable
            # No TDS only if BOTH this payment and the FY aggregate stay within limits.
            if net_payable <= config.tds_single_payment_limit and fy_aggregate <= config.tds_annual_limit:
                apply = False
        if apply:
            # Rate by grower entity type (1% Individual/HUF, 2% other). PAN
            # absence is only flagged, not rate-changed (per business rule).
            tds_rate = farm.tds_rate_pct
            tds_amount = (net_payable * tds_rate / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    amount_paid = (net_payable - tds_amount).quantize(Decimal('0.01'))

    # ─── SAVE ───
    # E5: a re-bill after reopen is the next version of this flock's settlement.
    from django.db.models import Max
    prev_version = BillVersion.objects.filter(flock=flock).aggregate(v=Max('version'))['v'] or 0
    # An admin's bill is approved as generated; a supervisor's waits for an admin.
    by_admin = bool(user and getattr(getattr(user, 'profile', None), 'is_admin', getattr(user, 'is_superuser', False)))
    bill = Bill.objects.create(
        flock=flock,
        version=prev_version + 1,
        generated_by=user,
        approval_status='approved' if by_admin else 'pending',
        approved_by=user if by_admin else None,
        approved_at=timezone.now() if by_admin else None,
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
        fcr_benchmark_adjustment=fcr_benchmark_adjustment,
        first_week_mortality_recovery=first_week_recovery,
        negligence_recovery=negligence_recovery,
        shortage_recovery=shortage_recovery,
        fcr_recovery=fcr_recovery,
        ifft_charges=ifft_charges,
        total_recoveries=total_recoveries,
        gross_payable=gross_payable.quantize(Decimal('0.01')),
        net_payable=net_payable,
        tds_rate_pct=tds_rate,
        tds_amount=tds_amount,
        tds_pan_missing=pan_missing,
        amount_paid=amount_paid,
        rate_card=config,
        config_snapshot={
            'rate_card_id': config.pk,
            'rate_card_name': config.label,
            'effective_from': config.effective_from.isoformat() if config.effective_from else None,
            'growing_method': config.growing_method,
            'standard_production_cost': str(config.standard_production_cost),
            'standard_growing_charges': str(config.standard_growing_charges),
            'min_growing_charges': str(config.min_growing_charges),
            'max_growing_charges': str(config.max_growing_charges) if config.max_growing_charges is not None else None,
            'gc_increase_pct': str(config.gc_increase_pct),
            'gc_decrease_pct': str(config.gc_decrease_pct),
            'grade_incentive_pct': str(config.grade_incentive_pct),
            'incentive_threshold_1': str(config.incentive_threshold_1),
            'incentive_threshold_2': str(config.incentive_threshold_2),
            'incentive_rate_1': str(config.incentive_rate_1),
            'incentive_rate_2': str(config.incentive_rate_2),
            'max_rate_incentive': str(config.max_rate_incentive),
            'chick_cost_per_bird': str(config.chick_cost_per_bird),
            'feed_cost_per_kg': str(config.feed_cost_per_kg),
            'admin_cost_per_chick': str(config.admin_cost_per_chick),
            'medicine_cost_per_chick': str(config.medicine_cost_per_chick),
            'medicine_use_actual': medicine_actual,
            'tds_rate_pct': str(tds_rate),
            'entity_type': farm.entity_type,
            'pan_present': farm.has_valid_pan,
        },
    )
    return bill
