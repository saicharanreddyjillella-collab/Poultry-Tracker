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
]


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='supervisor')
    phone = models.CharField(max_length=20, blank=True)
    assigned_farms = models.ManyToManyField('Farm', blank=True, related_name='assigned_supervisors')

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    @property
    def is_admin(self):
        return self.role == 'admin'

    def can_edit_farm(self, farm):
        if self.is_admin:
            return True
        return self.assigned_farms.filter(id=farm.id).exists()


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

    # Feed estimate per bird (kg) — soft target, not a hard limit
    bpsc_per_bird_kg = models.DecimalField(max_digits=6, decimal_places=3, default=0.5, help_text="Estimated BPSC per bird (kg)")
    bsc_per_bird_kg = models.DecimalField(max_digits=6, decimal_places=3, default=1.0, help_text="Estimated BSC per bird (kg)")
    # BFP = remaining (no fixed limit)

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.farm_id:
            farm = self.farm
            # Only validate on new active flocks
            if self.status == 'active' and not self.pk:
                if farm.has_active_flock:
                    raise ValidationError({'farm': 'This farm already has an active flock. Close the current flock first.'})
                if self.chick_count < farm.capacity_min or self.chick_count > farm.capacity_max:
                    raise ValidationError({
                        'chick_count': f'Chick count must be within ±5% of farm capacity ({farm.capacity}). '
                                       f'Acceptable range: {farm.capacity_min} — {farm.capacity_max}.'
                    })

    created_at = models.DateTimeField(auto_now_add=True)

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


class DailyEntry(models.Model):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='daily_entries')
    date = models.DateField()
    mortality_count = models.PositiveIntegerField(default=0)

    BAG_WEIGHT_KG = 50

    # Feed by type (in bags — each bag = 50 kg)
    feed_bpsc_bags = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="BPSC (bags)")
    feed_bsc_bags = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="BSC (bags)")
    feed_bfp_bags = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="BFP (bags)")

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
