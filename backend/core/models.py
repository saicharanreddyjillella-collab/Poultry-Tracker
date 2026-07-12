from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


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
        return self.assigned_farms.filter(id=farm.id).exists()

    def sync_farms_from_regions(self):
        """Auto-assign all farms in assigned regions to this user."""
        if self.assigned_regions:
            from django.db.models import Q
            region_farms = Farm.objects.filter(region__in=self.assigned_regions)
            # Add region farms without removing directly assigned ones
            for farm in region_farms:
                self.assigned_farms.add(farm)


class Farm(models.Model):
    SHED_TYPE_CHOICES = [
        ('EC', 'EC (Environmentally Controlled)'),
        ('OPEN', 'Open Shed'),
    ]

    farm_code = models.CharField(max_length=50, unique=True, default='', help_text="Unique farm code given by user")
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
    recovery_ifft = models.BooleanField(default=True, help_text="Apply IFFT charges per bag")
    medicine_use_actual = models.BooleanField(default=False, help_text="If ON: use actual medicine cost. If OFF: use chicks × medicine_cost_per_chick")

    created_at = models.DateTimeField(auto_now_add=True)

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


class Flock(models.Model):
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
        return self.chick_count - self.total_mortality - self.total_sold_birds

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
    def total_medication_cost(self):
        return self.medications.aggregate(total=models.Sum('cost'))['total'] or 0

    @property
    def flock_feed_stock(self):
        """Feed stock for this flock: delivered (assigned to flock OR unassigned on farm) + transfers in - consumed - transfers out"""
        from django.db.models import Sum, Q
        from django.apps import apps
        FeedOrderModel = apps.get_model('core', 'FeedOrder')
        FeedTransferModel = apps.get_model('core', 'FeedTransfer')

        # Delivered: orders assigned to this flock OR unassigned orders on this farm
        delivered = FeedOrderModel.objects.filter(
            Q(flock=self) | Q(farm=self.farm, flock__isnull=True),
            status='delivered'
        ).values('feed_type').annotate(t=Sum('quantity_bags'))
        del_map = {d['feed_type']: int(d['t']) for d in delivered}

        # If multiple active flocks, only count flock-assigned orders (not unassigned)
        active_count = self.farm.flocks.filter(status='active').count()
        if active_count > 1:
            delivered = FeedOrderModel.objects.filter(
                flock=self, status='delivered'
            ).values('feed_type').annotate(t=Sum('quantity_bags'))
            del_map = {d['feed_type']: int(d['t']) for d in delivered}

        # Consumed by this flock
        consumed = self.daily_entries.aggregate(
            bpsc=Sum('feed_bpsc_bags'), bsc=Sum('feed_bsc_bags'), bfp=Sum('feed_bfp_bags'),
        )

        # Transfers in
        t_in = FeedTransferModel.objects.filter(
            Q(to_flock=self) | Q(to_farm=self.farm, to_flock__isnull=True)
        ).values('feed_type').annotate(t=Sum('quantity_bags'))
        in_map = {t['feed_type']: int(t['t']) for t in t_in}

        # Transfers out
        t_out = FeedTransferModel.objects.filter(
            Q(from_flock=self) | Q(from_farm=self.farm, from_flock__isnull=True)
        ).values('feed_type').annotate(t=Sum('quantity_bags'))
        out_map = {t['feed_type']: int(t['t']) for t in t_out}

        if active_count > 1:
            t_in = FeedTransferModel.objects.filter(to_flock=self).values('feed_type').annotate(t=Sum('quantity_bags'))
            in_map = {t['feed_type']: int(t['t']) for t in t_in}
            t_out = FeedTransferModel.objects.filter(from_flock=self).values('feed_type').annotate(t=Sum('quantity_bags'))
            out_map = {t['feed_type']: int(t['t']) for t in t_out}

        bpsc = del_map.get('BPSC', 0) + in_map.get('BPSC', 0) - out_map.get('BPSC', 0) - (consumed['bpsc'] or 0)
        bsc = del_map.get('BSC', 0) + in_map.get('BSC', 0) - out_map.get('BSC', 0) - (consumed['bsc'] or 0)
        bfp = del_map.get('BFP', 0) + in_map.get('BFP', 0) - out_map.get('BFP', 0) - (consumed['bfp'] or 0)

        return {'bpsc': bpsc, 'bsc': bsc, 'bfp': bfp, 'total': bpsc + bsc + bfp}


class DailyEntry(models.Model):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='daily_entries')
    date = models.DateField()
    mortality_count = models.PositiveIntegerField(default=0)

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
        unique_together = ['flock', 'date']
        ordering = ['-date']

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


class Sale(models.Model):
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


class Medication(models.Model):
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

    def __str__(self):
        return f"{self.name} - {self.date}"


class FeedOrder(models.Model):
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

    def __str__(self):
        return f"{self.farm.farm_code} - {self.feed_type} x{self.quantity_bags} bags ({self.status})"


class FeedTransfer(models.Model):
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

    # Config snapshot
    config_snapshot = models.JSONField(default=dict)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"Bill: {self.flock.farm.farm_code} - {self.flock.placement_date} - ₹{self.net_payable}"
