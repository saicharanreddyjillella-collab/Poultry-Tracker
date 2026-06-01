from django.db import models
from django.contrib.auth.models import User


class Farm(models.Model):
    name = models.CharField(max_length=200)
    owner_name = models.CharField(max_length=200)
    location = models.CharField(max_length=300, blank=True)
    house_count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Flock(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
    ]
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='flocks')
    breed = models.CharField(max_length=100, blank=True)
    placement_date = models.DateField()
    chick_count = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
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
        return self.daily_entries.aggregate(total=models.Sum('feed_consumed_kg'))['total'] or 0

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
        """Feed Conversion Ratio = total feed / total weight of birds sold"""
        sold_kg = float(self.total_sold_weight_kg)
        if sold_kg == 0:
            return None
        return round(float(self.total_feed_kg) / sold_kg, 3)


class DailyEntry(models.Model):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='daily_entries')
    date = models.DateField()
    mortality_count = models.PositiveIntegerField(default=0)
    feed_consumed_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    water_consumed_liters = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    avg_body_weight_grams = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['flock', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.flock} - {self.date}"


class Sale(models.Model):
    """Records birds sold / lifted from a flock."""
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
    """Weekly feed rate update — applies across all flocks."""
    week_start_date = models.DateField(unique=True)
    rate_per_kg = models.DecimalField(max_digits=10, decimal_places=2, help_text="Cost per kg of feed in ₹")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-week_start_date']

    def __str__(self):
        return f"₹{self.rate_per_kg}/kg from {self.week_start_date}"


class Medication(models.Model):
    flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='medications')
    date = models.DateField()
    name = models.CharField(max_length=200)
    dose = models.CharField(max_length=100, blank=True)
    route = models.CharField(max_length=100, blank=True)
    reason = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} - {self.date}"
