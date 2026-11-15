from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

from .softdelete import SoftDeleteModel


FEED_TYPES = [
    ('BPSC', 'BPSC (Pre-Starter Crumble)'),
    ('BSC', 'BSC (Starter Crumble)'),
    ('BFP', 'BFP (Finisher Pellet)'),
]

ROLE_CHOICES = [
    ('admin', 'Admin'),
    ('supervisor', 'Supervisor'),
    ('plant', 'Feed Plant'),
]


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='supervisor')
    phone = models.CharField(max_length=20, blank=True)
    assigned_farms = models.ManyToManyField('Farm', blank=True, related_name='assigned_supervisors')
    assigned_regions = models.JSONField(default=list, blank=True, help_text="List of region names assigned to this supervisor")
    # Set when an admin creates the account or resets its password: the
    # password was chosen by someone else, so the user must pick their own.
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_plant(self):
        return self.role == 'plant'

    def can_edit_farm(self, farm):
        if self.is_admin:
            return True
        # Check by region first, then by direct assignment
        if farm.region and farm.region in (self.assigned_regions or []):
            return True
        if self.assigned_farms.filter(id=farm.id).exists():
            return True
        # Supervisor assigned to any active flock on this farm
        return farm.flocks.filter(supervisor=self.user, status='active').exists()

    def sync_farms_from_regions(self):
        """Auto-assign all farms in assigned regions to this user."""
        if self.assigned_regions:
            from django.db.models import Q
            region_farms = Farm.objects.filter(region__in=self.assigned_regions)
            # Add region farms without removing directly assigned ones
            for farm in region_farms:
                self.assigned_farms.add(farm)


class Farm(SoftDeleteModel):
    SHED_TYPE_CHOICES = [
        ('EC', 'EC (Environmentally Controlled)'),
        ('OPEN', 'Open Shed'),
    ]

    farm_code = models.CharField(max_length=50, default='', help_text="Unique farm code given by user (unique among live farms)")
    name = models.CharField(max_length=200)
    owner_name = models.CharField(max_length=200)
    shed_type = models.CharField(max_length=10, choices=SHED_TYPE_CHOICES, default='OPEN')
    region = models.CharField(max_length=200, blank=True, help_text="Region/area for grouping farms")
    location = models.CharField(max_length=300, blank=True)
    capacity = models.PositiveIntegerField(default=5000, help_text="Farm bird capacity")

    # Recovery flags — toggleable per farm
    recovery_excess_mortality = models.BooleanField(default=True, help_text="Apply 1st week excess mortality recovery")
    recovery_negligence = models.BooleanField(default=False, help_text="Apply farmer negligence recovery")
    recovery_shortage = models.BooleanField(default=True, help_text="Apply bird shortage recovery")
    recovery_fcr = models.BooleanField(default=True, help_text="Apply FCR recovery if exceeds area avg")
    fcr_benchmark_enabled = models.BooleanField(default=False, help_text="Apply fixed-benchmark FCR premium/deduction (independent of area-avg FCR recovery)")
    recovery_ifft = models.BooleanField(default=True, help_text="Apply IFFT charges per bag")
    medicine_use_actual = models.BooleanField(default=False, help_text="If ON: use actual medicine cost. If OFF: use chicks × medicine_cost_per_chick")

    # ── Grower tax identity (for TDS on growing charges) ──
    ENTITY_TYPE_CHOICES = [
        ('individual', 'Individual'),
        ('huf', 'HUF'),
        ('firm', 'Partnership / Firm'),
        ('company', 'Company'),
        ('llp', 'LLP'),
        ('fpo', 'FPO'),
        ('other', 'Other'),
    ]
    # Entity types taxed at the 1% TDS rate under Section 194C.
    INDIVIDUAL_HUF_TYPES = ('individual', 'huf')

    pan = models.CharField(max_length=10, blank=True, help_text="Grower PAN (10 chars). Used for TDS reporting.")
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES, default='individual', help_text="Grower entity type — drives the TDS rate (1% for Individual/HUF, 2% otherwise)")

    created_at = models.DateTimeField(auto_now_add=True)

    # E14
    SOFT_DELETE_CHILDREN = ('flocks', 'feed_orders', 'documents')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['farm_code'], condition=models.Q(deleted_at__isnull=True),
                                               name='uniq_live_farm_code')]

    def check_can_delete(self):
        from .billlock import BillLocked
        if Flock.all_objects.filter(farm=self).filter(
                models.Q(bill__isnull=False) | models.Q(bill_versions__isnull=False)).exists():
            raise BillLocked(f'Farm {self.farm_code} has settled (billed) flocks, so it can\'t be deleted — '
                             'its settlement history must stay on record.')

    def restore_conflict(self):
        if Farm.objects.filter(farm_code=self.farm_code).exclude(pk=self.pk).exists():
            return (f'A farm with code {self.farm_code} already exists. Change that farm\'s code '
                    'before restoring this one.')

    def __str__(self):
        return f"{self.farm_code} - {self.name}"

    @property
    def capacity_min(self):
        """Minimum acceptable chick count (capacity - 5%)"""
        return int(self.capacity * 0.95)

    @property
    def capacity_max(self):
        """Maximum acceptable chick count (capacity + 5%)"""
        return int(self.capacity * 1.05)

    @property
    def has_active_flock(self):
        return self.flocks.filter(status='active').exists()


    PAN_REGEX = r'^[A-Z]{5}[0-9]{4}[A-Z]$'

    @property
    def has_valid_pan(self):
        import re
        return bool(self.pan) and bool(re.match(self.PAN_REGEX, self.pan.upper()))

    @property
    def is_individual_huf(self):
        return self.entity_type in self.INDIVIDUAL_HUF_TYPES

    @property
    def tds_rate_pct(self):
        """Section 194C TDS rate: 1% for Individual/HUF, 2% for others."""
        from decimal import Decimal
        return Decimal('1') if self.is_individual_huf else Decimal('2')


class Flock(SoftDeleteModel):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
    ]
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='flocks')
    placement_date = models.DateField()
    chick_count = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='supervised_flocks')

    # Feed estimate per bird (kg) — soft target, not a hard limit
    bpsc_per_bird_kg = models.DecimalField(max_digits=6, decimal_places=3, default=0.5, help_text="Estimated BPSC per bird (kg)")
    bsc_per_bird_kg = models.DecimalField(max_digits=6, decimal_places=3, default=1.0, help_text="Estimated BSC per bird (kg)")
    # BFP = remaining (no fixed limit)

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.farm_id:
            farm = self.farm
            if self.status == 'active' and not self.pk:
                # Check total active chicks + this new flock <= farm capacity
                existing_active_chicks = sum(
                    f.chick_count for f in farm.flocks.filter(status='active')
                )
                if existing_active_chicks + self.chick_count > farm.capacity:
                    remaining = farm.capacity - existing_active_chicks
                    raise ValidationError({
                        'chick_count': f'Farm capacity is {farm.capacity}. Active flocks already have {existing_active_chicks} chicks. '
                                       f'Maximum for this flock: {remaining}.'
                    })

    # E14
    SOFT_DELETE_CHILDREN = ('daily_entries', 'sales', 'medications', 'documents')

    def check_can_delete(self):
        from .billlock import BillLocked
        if Bill.objects.filter(flock_id=self.pk).exists() or BillVersion.objects.filter(flock_id=self.pk).exists():
            raise BillLocked(f'Flock #{self.pk} has a bill (or bill history), so it can\'t be deleted — '
                             'its settlement must stay on record.')

    def restore_parents(self):
        return [Farm.all_objects.get(pk=self.farm_id)]

    def __str__(self):
        return f"{self.farm.name} - {self.placement_date}"

    @property
    def age_days(self):
        from datetime import date
        return (date.today() - self.placement_date).days

    @property
    def total_mortality(self):
        return self.daily_entries.aggregate(total=models.Sum('mortality_count'))['total'] or 0

    @property
    def total_culls(self):
        return self.daily_entries.aggregate(total=models.Sum('cull_count'))['total'] or 0

    @property
    def cull_percentage(self):
        if self.chick_count == 0:
            return 0
        return round((self.total_culls / self.chick_count) * 100, 2)

    @property
    def total_feed_kg(self):
        agg = self.daily_entries.aggregate(
            bpsc=models.Sum('feed_bpsc_bags'),
            bsc=models.Sum('feed_bsc_bags'),
            bfp=models.Sum('feed_bfp_bags'),
        )
        total_bags = float(agg['bpsc'] or 0) + float(agg['bsc'] or 0) + float(agg['bfp'] or 0)
        return total_bags * 50

    @property
    def feed_by_type(self):
        agg = self.daily_entries.aggregate(
            bpsc=models.Sum('feed_bpsc_bags'),
            bsc=models.Sum('feed_bsc_bags'),
            bfp=models.Sum('feed_bfp_bags'),
        )
        return {
            'bpsc_bags': float(agg['bpsc'] or 0),
            'bsc_bags': float(agg['bsc'] or 0),
            'bfp_bags': float(agg['bfp'] or 0),
            'bpsc_kg': float(agg['bpsc'] or 0) * 50,
            'bsc_kg': float(agg['bsc'] or 0) * 50,
            'bfp_kg': float(agg['bfp'] or 0) * 50,
        }

    @property
    def feed_schedule_status(self):
        """How much of each feed type has been used vs estimated target."""
        fb = self.feed_by_type
        bpsc_est = float(self.bpsc_per_bird_kg) * self.chick_count
        bsc_est = float(self.bsc_per_bird_kg) * self.chick_count
        return {
            'bpsc_used_kg': fb['bpsc_kg'],
            'bpsc_used_bags': fb['bpsc_bags'],
            'bpsc_estimate_kg': round(bpsc_est, 2),
            'bpsc_estimate_bags': round(bpsc_est / 50, 2),
            'bpsc_remaining_kg': round(max(0, bpsc_est - fb['bpsc_kg']), 2),
            'bsc_used_kg': fb['bsc_kg'],
            'bsc_used_bags': fb['bsc_bags'],
            'bsc_estimate_kg': round(bsc_est, 2),
            'bsc_estimate_bags': round(bsc_est / 50, 2),
            'bsc_remaining_kg': round(max(0, bsc_est - fb['bsc_kg']), 2),
            'bfp_used_kg': fb['bfp_kg'],
            'bfp_used_bags': fb['bfp_bags'],
            'current_feed_type': 'BPSC' if fb['bpsc_kg'] < bpsc_est else ('BSC' if fb['bsc_kg'] < bsc_est else 'BFP'),
        }

    @property
    def total_sold_birds(self):
        return self.sales.aggregate(total=models.Sum('bird_count'))['total'] or 0

    @property
    def total_sold_weight_kg(self):
        return self.sales.aggregate(total=models.Sum('total_weight_kg'))['total'] or 0

    @property
    def mortality_percentage(self):
        if self.chick_count == 0:
            return 0
        return round((self.total_mortality / self.chick_count) * 100, 2)

    @property
    def livability_percentage(self):
        return round(100 - self.mortality_percentage, 2)

    @property
    def live_birds(self):
        return self.chick_count - self.total_mortality - self.total_culls - self.total_sold_birds

    @property
    def reconciliation(self):
        """Daily bird-population reconciliation.

        opening - mortality - culls - sold = closing (expected live birds).
        is_balanced is False when total losses + sales exceed the opening
        count, i.e. the computed closing would be negative, which signals a
        data-entry error (an over-counted sale or mortality figure).
        """
        opening = self.chick_count
        mortality = self.total_mortality
        culls = self.total_culls
        sold = self.total_sold_birds
        accounted = mortality + culls + sold
        closing = opening - accounted
        return {
            'opening': opening,
            'mortality': mortality,
            'culls': culls,
            'sold': sold,
            'accounted': accounted,
            'closing': closing,
            'is_balanced': closing >= 0,
            'overcount': max(0, -closing),
        }

    @property
    def weight_vs_standard(self):
        """Latest recorded body weight vs the Cobb-400 standard for that age.

        Returns None if no body weight has been recorded. status is
        'on_track' within +/-3% of standard, else 'above' / 'below'.
        """
        from .standards import get_standard_weight
        entry = (self.daily_entries
                 .exclude(avg_body_weight_grams__isnull=True)
                 .order_by('-date').first())
        if entry is None or entry.avg_body_weight_grams is None:
            return None
        day = (entry.date - self.placement_date).days
        actual = float(entry.avg_body_weight_grams)
        standard = float(get_standard_weight(day))
        variance_g = round(actual - standard, 1)
        variance_pct = round((variance_g / standard) * 100, 1) if standard else 0
        if variance_pct > 3:
            status = 'above'
        elif variance_pct < -3:
            status = 'below'
        else:
            status = 'on_track'
        return {
            'day': day,
            'date': str(entry.date),
            'actual_g': actual,
            'standard_g': standard,
            'variance_g': variance_g,
            'variance_pct': variance_pct,
            'status': status,
        }

    @property
    def scorecard(self):
        """Unified flock performance scorecard.

        Composes the metrics that are available into component scores
        (0-100) and an overall rating. Works for active and closed flocks;
        components that need a closed flock (EPEF, farmer grade) are only
        included once present.
        """
        components = []  # list of (label, score 0-100, detail)

        # Livability (always available): 100% - mortality% - cull% vs a
        # ~95% healthy benchmark (5% standard mortality). Culls count as loss.
        survived_pct = 100 - float(self.mortality_percentage) - float(self.cull_percentage)
        liv_score = max(0.0, min(100.0, (survived_pct / 95.0) * 100))
        components.append(('livability', round(liv_score, 1),
                           f'{round(survived_pct, 1)}% survived'))

        # Weight vs standard (once a weight is recorded).
        wvs = self.weight_vs_standard
        if wvs is not None:
            pct = wvs['variance_pct']
            # on target = 100; scale down ~2 points per % below, cap bonus at 100.
            wt_score = max(0.0, min(100.0, 100 + pct * 2))
            components.append(('weight', round(wt_score, 1),
                               f"{'+' if pct > 0 else ''}{pct}% vs target"))

        # EPEF (closed flocks): 400 -> 100, 300 -> 50, linear, capped.
        epef = self.epef
        if epef is not None:
            epef_score = max(0.0, min(100.0, (epef - 200) / 2.0))
            components.append(('epef', round(epef_score, 1), f'EPEF {epef}'))

        # FCR (closed flocks) vs 1.65 standard: at/below standard = 100,
        # each 0.1 above drops ~15 points.
        fcr = self.fcr
        if fcr is not None:
            std_fcr = 1.65
            fcr_score = max(0.0, min(100.0, 100 - max(0.0, (fcr - std_fcr)) * 150))
            components.append(('fcr', round(fcr_score, 1), f'FCR {fcr}'))

        overall = round(sum(c[1] for c in components) / len(components), 1) if components else 0.0
        if overall >= 85:
            rating = 'Excellent'
        elif overall >= 70:
            rating = 'Good'
        elif overall >= 50:
            rating = 'Fair'
        else:
            rating = 'Poor'

        # Farmer grade from the bill, if generated (closed flocks).
        farmer_grade = None
        try:
            farmer_grade = self.bill.farmer_grade
        except Exception:
            farmer_grade = None

        return {
            'overall_score': overall,
            'rating': rating,
            'farmer_grade': farmer_grade,
            'components': [
                {'label': l, 'score': sc, 'detail': d} for (l, sc, d) in components
            ],
        }

    @property
    def water_alerts(self):
        """Daily entries whose water:feed ratio is outside the normal band.

        Returns a list (most recent first) of {date, day, ratio, status,
        water_liters, feed_kg} for every entry flagged 'low' or 'high'.
        """
        alerts = []
        for e in self.daily_entries.all():  # Meta ordering is -date
            status = e.water_feed_status
            if status in ('low', 'high'):
                alerts.append({
                    'date': str(e.date),
                    'day': (e.date - self.placement_date).days,
                    'ratio': e.water_feed_ratio,
                    'status': status,
                    'water_liters': float(e.water_consumed_liters),
                    'feed_kg': e.total_feed_kg,
                })
        return alerts

    @property
    def fcr(self):
        """FCR only calculated for closed flocks."""
        if self.status != 'closed':
            return None
        sold_kg = float(self.total_sold_weight_kg)
        if sold_kg == 0:
            return None
        return round(float(self.total_feed_kg) / sold_kg, 3)

    @property
    def avg_sold_weight_kg(self):
        """Average live weight per bird sold (kg). None if nothing sold."""
        birds = self.total_sold_birds
        if not birds:
            return None
        return round(float(self.total_sold_weight_kg) / birds, 3)

    @property
    def epef(self):
        """European Production Efficiency Factor (European Broiler Index).

        EPEF = (Livability % x Avg live weight kg x 100) / (Age days x FCR)
        Higher is better (~400+ good). Only meaningful for a closed flock.
        """
        fcr = self.fcr
        avg_wt = self.avg_sold_weight_kg
        age = self.age_days
        if fcr is None or not fcr or avg_wt is None or not age:
            return None
        livability = float(self.livability_percentage)
        return round((livability * avg_wt * 100) / (age * fcr), 1)

    @property
    def total_medication_cost(self):
        return self.medications.aggregate(total=models.Sum('cost'))['total'] or 0

    @property
    def flock_feed_stock(self):
        """Feed stock for THIS flock only = delivered to this flock + transfers in - consumed - transfers out."""
        from django.db.models import Sum
        from django.apps import apps
        FeedOrderModel = apps.get_model('core', 'FeedOrder')
        FeedTransferModel = apps.get_model('core', 'FeedTransfer')

        # Only orders assigned to this flock
        delivered = FeedOrderModel.objects.filter(
            flock=self, status='delivered'
        ).values('feed_type').annotate(t=Sum('quantity_bags'))
        del_map = {d['feed_type']: int(d['t']) for d in delivered}

        # This flock's consumption
        consumed = self.daily_entries.aggregate(
            bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'),
        )

        # Transfers in to this flock
        t_in = FeedTransferModel.objects.filter(to_flock=self).values('feed_type').annotate(t=Sum('quantity_bags'))
        in_map = {t['feed_type']: int(t['t']) for t in t_in}

        # Transfers out from this flock
        t_out = FeedTransferModel.objects.filter(from_flock=self).values('feed_type').annotate(t=Sum('quantity_bags'))
        out_map = {t['feed_type']: int(t['t']) for t in t_out}

        bpsc = del_map.get('BPSC', 0) + in_map.get('BPSC', 0) - out_map.get('BPSC', 0) - (consumed['bpsc'] or 0)
        bsc = del_map.get('BSC', 0) + in_map.get('BSC', 0) - out_map.get('BSC', 0) - (consumed['bsc'] or 0)
        bfp = del_map.get('BFP', 0) + in_map.get('BFP', 0) - out_map.get('BFP', 0) - (consumed['bfp'] or 0)

        return {'bpsc': bpsc, 'bsc': bsc, 'bfp': bfp, 'total': bpsc + bsc + bfp}

    @property
    def feed_reconciliation(self):
        """Reconcile feed DISPATCHED to this flock against feed CONSUMED.

        dispatched = delivered orders + transfers in - transfers out.
        consumed   = sum of daily-entry feed bags.
        variance   = dispatched - consumed (bags). A positive variance is
        feed sent but not fed here (possible diversion or just unused stock
        still on hand); a negative variance is feed fed that was never
        recorded as dispatched (under-recorded dispatch / mill under-fill,
        which flatters FCR).

        status is 'balanced' when |variance| is within the configured
        tolerance of dispatched, else 'over_dispatched' / 'under_dispatched'.
        Tolerance comes from the active BillConfig.
        """
        from django.db.models import Sum
        from django.apps import apps
        FeedOrderModel = apps.get_model('core', 'FeedOrder')
        FeedTransferModel = apps.get_model('core', 'FeedTransfer')

        delivered = FeedOrderModel.objects.filter(flock=self, status='delivered') \
            .values('feed_type').annotate(t=Sum('quantity_bags'))
        del_map = {d['feed_type']: int(d['t']) for d in delivered}
        t_in = {t['feed_type']: int(t['t']) for t in
                FeedTransferModel.objects.filter(to_flock=self).values('feed_type').annotate(t=Sum('quantity_bags'))}
        t_out = {t['feed_type']: int(t['t']) for t in
                 FeedTransferModel.objects.filter(from_flock=self).values('feed_type').annotate(t=Sum('quantity_bags'))}
        consumed = self.daily_entries.aggregate(
            BPSC=Sum('feed_bpsc_bags'), BSC=Sum('feed_bsc_bags'), BFP=Sum('feed_bfp_bags'),
        )

        by_type = {}
        disp_total = cons_total = 0
        for ft in ('BPSC', 'BSC', 'BFP'):
            disp = del_map.get(ft, 0) + t_in.get(ft, 0) - t_out.get(ft, 0)
            cons = consumed.get(ft) or 0
            by_type[ft] = {'dispatched': disp, 'consumed': cons, 'variance': disp - cons}
            disp_total += disp
            cons_total += cons

        variance = disp_total - cons_total
        variance_pct = round((variance / disp_total) * 100, 1) if disp_total else 0.0

        # Tolerance from active config (fall back to 5%).
        try:
            BillConfigModel = apps.get_model('core', 'BillConfig')
            tol = float(BillConfigModel.get_active().feed_reconciliation_tolerance_pct)
        except Exception:
            tol = 5.0

        if abs(variance_pct) <= tol:
            status = 'balanced'
        elif variance > 0:
            status = 'over_dispatched'
        else:
            status = 'under_dispatched'

        return {
            'dispatched_bags': disp_total,
            'consumed_bags': cons_total,
            'variance_bags': variance,
            'variance_pct': variance_pct,
            'tolerance_pct': tol,
            'status': status,
            'is_balanced': status == 'balanced',
            'by_type': by_type,
        }


class DailyEntry(SoftDeleteModel):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='daily_entries')
    date = models.DateField()
    mortality_count = models.PositiveIntegerField(default=0)
    cull_count = models.PositiveIntegerField(default=0, help_text="Birds intentionally removed (culled), tracked separately from deaths")

    BAG_WEIGHT_KG = 50

    # Feed by type (in bags — each bag = 50 kg)
    feed_bpsc_bags = models.PositiveIntegerField(default=0, verbose_name="BPSC (bags)")
    feed_bsc_bags = models.PositiveIntegerField(default=0, verbose_name="BSC (bags)")
    feed_bfp_bags = models.PositiveIntegerField(default=0, verbose_name="BFP (bags)")

    water_consumed_liters = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    avg_body_weight_grams = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        # E14: one live entry per flock per day (deleted entries don't block re-entry)
        constraints = [models.UniqueConstraint(fields=['flock', 'date'], condition=models.Q(deleted_at__isnull=True),
                                               name='uniq_live_entry_per_flock_day')]

    def restore_parents(self):
        return [Flock.all_objects.get(pk=self.flock_id)]

    def restore_conflict(self):
        if DailyEntry.objects.filter(flock_id=self.flock_id, date=self.date).exclude(pk=self.pk).exists():
            return f'A newer entry for {self.date} already exists on this flock. Delete it before restoring this one.'

    def __str__(self):
        return f"{self.flock} - {self.date}"

    def clean(self):
        from django.core.exceptions import ValidationError
        from datetime import date as dt_date
        errors = {}
        if self.date and self.date > dt_date.today():
            errors['date'] = 'Date cannot be in the future.'
        if self.flock_id:
            flock = self.flock
            if self.date and self.date < flock.placement_date:
                errors['date'] = 'Date cannot be before placement date.'
            if self.mortality_count and self.mortality_count > flock.live_birds:
                errors['mortality_count'] = f'Mortality ({self.mortality_count}) exceeds live birds ({flock.live_birds}).'
        if errors:
            raise ValidationError(errors)

    @property
    def feed_bpsc_kg(self):
        return float(self.feed_bpsc_bags) * self.BAG_WEIGHT_KG

    @property
    def feed_bsc_kg(self):
        return float(self.feed_bsc_bags) * self.BAG_WEIGHT_KG

    @property
    def feed_bfp_kg(self):
        return float(self.feed_bfp_bags) * self.BAG_WEIGHT_KG

    @property
    def total_feed_bags(self):
        return float(self.feed_bpsc_bags) + float(self.feed_bsc_bags) + float(self.feed_bfp_bags)

    @property
    def total_feed_kg(self):
        return self.total_feed_bags * self.BAG_WEIGHT_KG

    # Normal broiler water:feed ratio is ~1.6-2.0 L water per kg feed.
    # Outside this band can signal illness/under-drinking (low) or heat
    # stress / water spillage (high).
    WATER_FEED_LOW = 1.2
    WATER_FEED_HIGH = 2.5

    @property
    def water_feed_ratio(self):
        """Litres of water per kg of feed for this day. None if no feed."""
        feed_kg = self.total_feed_kg
        if not feed_kg:
            return None
        return round(float(self.water_consumed_liters) / feed_kg, 2)

    @property
    def water_feed_status(self):
        """'normal', 'low', 'high', or None (when the ratio can't be computed)."""
        ratio = self.water_feed_ratio
        if ratio is None:
            return None
        if ratio < self.WATER_FEED_LOW:
            return 'low'
        if ratio > self.WATER_FEED_HIGH:
            return 'high'
        return 'normal'


class Sale(SoftDeleteModel):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='sales')
    date = models.DateField()
    bird_count = models.PositiveIntegerField()
    total_weight_kg = models.DecimalField(max_digits=12, decimal_places=2)
    rate_per_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    trader_name = models.CharField(max_length=200, blank=True, help_text="Trader/buyer name")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def restore_parents(self):
        return [Flock.all_objects.get(pk=self.flock_id)]

    def __str__(self):
        return f"{self.flock} - {self.date} - {self.bird_count} birds"

    @property
    def total_amount(self):
        if self.rate_per_kg:
            return round(float(self.total_weight_kg) * float(self.rate_per_kg), 2)
        return None

    @property
    def avg_bird_weight_kg(self):
        if self.bird_count > 0:
            return round(float(self.total_weight_kg) / self.bird_count, 3)
        return 0


class FeedRate(models.Model):
    FEED_TYPE_CHOICES = FEED_TYPES
    week_start_date = models.DateField()
    feed_type = models.CharField(max_length=10, choices=FEED_TYPE_CHOICES, default='BFP')
    rate_per_kg = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost per kg in ₹")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['week_start_date', 'feed_type']
        ordering = ['-week_start_date', 'feed_type']

    def __str__(self):
        return f"{self.feed_type} ₹{self.rate_per_kg}/kg from {self.week_start_date}"


class Medication(SoftDeleteModel):
    ROUTE_CHOICES = [
        ('water', 'Drinking Water'),
        ('feed', 'Feed'),
        ('injection', 'Injection'),
        ('spray', 'Spray'),
        ('eye_drop', 'Eye Drop'),
        ('other', 'Other'),
    ]
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='medications')
    date = models.DateField()
    name = models.CharField(max_length=200)
    dose = models.CharField(max_length=100, blank=True)
    route = models.CharField(max_length=20, choices=ROUTE_CHOICES, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Total cost in ₹")
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-date']

    def restore_parents(self):
        return [Flock.all_objects.get(pk=self.flock_id)]

    def __str__(self):
        return f"{self.name} - {self.date}"


class FeedOrder(SoftDeleteModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='feed_orders')
    flock = models.ForeignKey('Flock', on_delete=models.SET_NULL, null=True, blank=True, related_name='feed_orders', help_text="Which flock this feed is for")
    feed_type = models.CharField(max_length=10, choices=FEED_TYPES)
    quantity_bags = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    ordered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='feed_orders')
    order_date = models.DateTimeField(auto_now_add=True)
    sent_date = models.DateTimeField(null=True, blank=True)
    delivered_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-order_date']

    def restore_parents(self):
        parents = [Farm.all_objects.get(pk=self.farm_id)]
        if self.flock_id:
            parents.append(Flock.all_objects.get(pk=self.flock_id))
        return parents

    def __str__(self):
        return f"{self.farm.farm_code} - {self.feed_type} x{self.quantity_bags} bags ({self.status})"


class FeedTransfer(SoftDeleteModel):
    from_farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='feed_transfers_out')
    to_farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='feed_transfers_in')
    from_flock = models.ForeignKey('Flock', on_delete=models.SET_NULL, null=True, blank=True, related_name='feed_transfers_out')
    to_flock = models.ForeignKey('Flock', on_delete=models.SET_NULL, null=True, blank=True, related_name='feed_transfers_in')
    feed_type = models.CharField(max_length=10, choices=FEED_TYPES)
    quantity_bags = models.PositiveIntegerField()
    date = models.DateField()
    transferred_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def restore_parents(self):
        parents = [Farm.all_objects.get(pk=self.from_farm_id), Farm.all_objects.get(pk=self.to_farm_id)]
        for fid in (self.from_flock_id, self.to_flock_id):
            if fid:
                parents.append(Flock.all_objects.get(pk=fid))
        return parents

    def __str__(self):
        return f"{self.from_farm.farm_code} → {self.to_farm.farm_code}: {self.feed_type} x{self.quantity_bags}"


class BillConfig(models.Model):
    """Configurable billing rates — only one active config at a time."""
    chick_cost_per_bird = models.DecimalField(max_digits=10, decimal_places=2, default=34.00)
    feed_cost_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=44.00)
    admin_cost_per_chick = models.DecimalField(max_digits=10, decimal_places=2, default=6.00)
    medicine_cost_per_chick = models.DecimalField(max_digits=10, decimal_places=2, default=5.00, help_text="Default medicine cost per chick when not using actual")
    standard_fcr = models.DecimalField(max_digits=5, decimal_places=2, default=1.65)
    standard_mortality_pct = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    standard_production_cost = models.DecimalField(max_digits=10, decimal_places=2, default=95.00)
    standard_growing_charges = models.DecimalField(max_digits=10, decimal_places=2, default=6.50)
    min_growing_charges = models.DecimalField(max_digits=10, decimal_places=2, default=4.50)

    # Rate incentive thresholds
    incentive_threshold_1 = models.DecimalField(max_digits=10, decimal_places=2, default=110.00)
    incentive_threshold_2 = models.DecimalField(max_digits=10, decimal_places=2, default=120.00)
    incentive_rate_1 = models.DecimalField(max_digits=5, decimal_places=2, default=0.05, help_text="Per rupee per kg between threshold 1 and 2")
    incentive_rate_2 = models.DecimalField(max_digits=5, decimal_places=2, default=0.10, help_text="Per rupee per kg above threshold 2")
    max_rate_incentive = models.DecimalField(max_digits=10, decimal_places=2, default=2.50)

    # Recovery rates
    first_week_mortality_limit_pct = models.DecimalField(max_digits=5, decimal_places=2, default=1.50)
    first_week_recovery_per_chick = models.DecimalField(max_digits=10, decimal_places=2, default=34.00)
    negligence_rate_1_15 = models.DecimalField(max_digits=10, decimal_places=2, default=80.00)
    negligence_rate_16_20 = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    negligence_rate_21_35 = models.DecimalField(max_digits=10, decimal_places=2, default=170.00)
    negligence_rate_above_35 = models.DecimalField(max_digits=10, decimal_places=2, default=190.00)
    ifft_per_bag = models.DecimalField(max_digits=10, decimal_places=2, default=25.00)

    # Grade thresholds
    grade_a_plus_max = models.DecimalField(max_digits=10, decimal_places=2, default=94.00)
    grade_a_max = models.DecimalField(max_digits=10, decimal_places=2, default=95.00)
    grade_b_max = models.DecimalField(max_digits=10, decimal_places=2, default=96.00)
    grade_c_max = models.DecimalField(max_digits=10, decimal_places=2, default=97.00)
    grade_d_max = models.DecimalField(max_digits=10, decimal_places=2, default=98.00)
    grade_incentive_pct = models.DecimalField(max_digits=5, decimal_places=2, default=50.00, help_text="% increase for A+/A, decrease for B/C/D")

    # ── TDS on growing charges (Section 194C) ──
    apply_tds = models.BooleanField(default=True, help_text="Deduct TDS on the net amount payable to the grower")
    apply_tds_thresholds = models.BooleanField(default=True, help_text="If ON, skip TDS when this bill <= single limit AND the grower's FY total <= annual limit")
    tds_single_payment_limit = models.DecimalField(max_digits=12, decimal_places=2, default=30000.00, help_text="Per-payment TDS threshold (Sec 194C)")
    tds_annual_limit = models.DecimalField(max_digits=12, decimal_places=2, default=100000.00, help_text="Annual aggregate TDS threshold per grower (Sec 194C)")

    # ── Feed-lot reconciliation ──
    feed_reconciliation_tolerance_pct = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, help_text="Allowed % gap between feed dispatched and consumed before a flock is flagged")

    # ── FCR benchmark band (premium for beating, deduction for missing) ──
    fcr_benchmark = models.DecimalField(max_digits=5, decimal_places=2, default=1.75, help_text="Target FCR; beating earns a premium, missing a deduction")
    fcr_benchmark_tolerance_pct = models.DecimalField(max_digits=5, decimal_places=2, default=5.00, help_text="Neutral band around the benchmark (± %); no adjustment inside it")
    fcr_premium_per_kg_per_step = models.DecimalField(max_digits=6, decimal_places=3, default=0.300, help_text="₹/kg premium per 0.1 FCR below the band")
    fcr_deduction_per_kg_per_step = models.DecimalField(max_digits=6, decimal_places=3, default=0.300, help_text="₹/kg deduction per 0.1 FCR above the band")
    fcr_benchmark_max_adjustment_per_kg = models.DecimalField(max_digits=6, decimal_places=3, default=2.000, help_text="Cap on the per-kg premium/deduction magnitude")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Bill Config (chick ₹{self.chick_cost_per_bird}, feed ₹{self.feed_cost_per_kg}/kg)"

    @classmethod
    def get_active(cls):
        config = cls.objects.filter(is_active=True).first()
        if not config:
            config = cls.objects.create()
        return config


class Bill(models.Model):
    """Generated bill when a flock is closed."""
    flock = models.OneToOneField(Flock, on_delete=models.CASCADE, related_name='bill')
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    # Flock summary
    chicks_placed = models.PositiveIntegerField()
    total_mortality = models.PositiveIntegerField()
    live_birds = models.PositiveIntegerField()
    total_sold_birds = models.PositiveIntegerField()
    total_sold_weight_kg = models.DecimalField(max_digits=12, decimal_places=2)
    avg_selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    age_days = models.PositiveIntegerField()

    # Feed
    total_feed_kg = models.DecimalField(max_digits=12, decimal_places=2)
    total_feed_bags = models.DecimalField(max_digits=12, decimal_places=2)

    # Cost breakdown
    chick_cost = models.DecimalField(max_digits=12, decimal_places=2)
    feed_cost = models.DecimalField(max_digits=12, decimal_places=2)
    medicine_cost = models.DecimalField(max_digits=12, decimal_places=2)
    admin_cost = models.DecimalField(max_digits=12, decimal_places=2)
    production_cost_total = models.DecimalField(max_digits=12, decimal_places=2)
    production_cost_per_kg = models.DecimalField(max_digits=10, decimal_places=2)

    # Growing charges
    farmer_grade = models.CharField(max_length=5)
    growing_charges_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    growing_charges_total = models.DecimalField(max_digits=12, decimal_places=2)

    # Rate incentive
    rate_incentive_per_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rate_incentive_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # FCR benchmark band (signed: + premium / - deduction)
    fcr_benchmark_adjustment = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Recoveries
    first_week_mortality_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    negligence_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shortage_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fcr_recovery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ifft_charges = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_recoveries = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Final
    gross_payable = models.DecimalField(max_digits=12, decimal_places=2)
    net_payable = models.DecimalField(max_digits=12, decimal_places=2)

    # TDS (Section 194C) — deducted from net_payable
    tds_rate_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tds_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tds_pan_missing = models.BooleanField(default=False, help_text="Grower had no valid PAN when this bill was generated")
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="net_payable minus TDS")

    # Config snapshot
    config_snapshot = models.JSONField(default=dict)
    notes = models.TextField(blank=True)

    # E5: 1 for the first settlement; +1 each time the flock is reopened and re-billed
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"Bill: {self.flock.farm.farm_code} - {self.flock.placement_date} - ₹{self.net_payable}"


class BillVersion(models.Model):
    """A superseded bill, archived when an admin reopens a settled flock (E5).

    Append-only: never edited or deleted (enforced in core.billlock)."""
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='bill_versions')
    version = models.PositiveIntegerField()
    data = models.JSONField(help_text="Full snapshot of the bill as it was before reopening")
    net_payable = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    generated_at = models.DateTimeField(null=True, blank=True)
    reopened_at = models.DateTimeField(auto_now_add=True)
    reopened_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='bill_reopens')
    reason = models.TextField()

    class Meta:
        ordering = ['flock', 'version']
        constraints = [models.UniqueConstraint(fields=['flock', 'version'], name='uniq_bill_version_per_flock')]

    def __str__(self):
        return f"BillVersion v{self.version}: flock {self.flock_id} - ₹{self.net_payable}"


def document_upload_path(instance, filename):
    """media/documents/farm_<id>/ or flock_<id>/<filename>."""
    if instance.farm_id:
        return f"documents/farm_{instance.farm_id}/{filename}"
    if instance.flock_id:
        return f"documents/flock_{instance.flock_id}/{filename}"
    return f"documents/misc/{filename}"


class Document(SoftDeleteModel):
    """A file attached to a farm or a flock (agreement, KYC, vet certificate, etc.)."""
    DOC_TYPE_CHOICES = [
        ('agreement', 'Farmer Agreement'),
        ('kyc', 'KYC / ID Proof'),
        ('bank', 'Bank Proof'),
        ('vet_certificate', 'Vet / Cull Certificate'),
        ('invoice', 'Invoice / Bill Copy'),
        ('other', 'Other'),
    ]

    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES, default='other')
    title = models.CharField(max_length=200, blank=True, help_text="Short label; defaults to the file name")
    file = models.FileField(upload_to=document_upload_path)
    original_name = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def restore_parents(self):
        if self.farm_id:
            return [Farm.all_objects.get(pk=self.farm_id)]
        if self.flock_id:
            return [Flock.all_objects.get(pk=self.flock_id)]
        return []

    def __str__(self):
        target = f"farm {self.farm_id}" if self.farm_id else f"flock {self.flock_id}"
        return f"{self.get_doc_type_display()} ({target})"

    @property
    def owning_farm(self):
        """The farm this document belongs to, directly or via its flock."""
        if self.farm_id:
            return self.farm
        if self.flock_id:
            return self.flock.farm
        return None


class AuditLog(models.Model):
    """Who changed what, when — recorded automatically for money-affecting
    records (see core/audit.py). Rows are append-only; never edited."""
    ACTION_CHOICES = [('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'), ('restore', 'Restore')]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='audit_entries')
    actor_username = models.CharField(max_length=150, blank=True,
                                      help_text="Kept even if the user is later deleted")
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model = models.CharField(max_length=60, db_index=True)
    object_id = models.CharField(max_length=40, db_index=True)
    object_repr = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True,
                               help_text="update: {field: [before, after]}; create/delete: full snapshot")

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} {self.model}#{self.object_id} by {self.actor_username or 'system'}"
