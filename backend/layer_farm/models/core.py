"""
Layer Farm domain models — per-flock cost accumulation + egg output.

A layer flock is a long-running cost centre: a long feeding-only phase, then a
long laying phase. Everything sent to a flock (chicks, feed valued at batch
cost, medicine, vaccine, overhead share) accumulates as its cost. Eggs produced
and egg sales accumulate as its output. Each record links to the accounting
Voucher the service posts.

BUSINESS = 'layer'.
"""
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from accounting.models import Party, Voucher
from inventory.models import Item, Unit

BUSINESS = 'layer'


class LayerFarm(models.Model):
    """A physical layer farm/shed. Can run multiple flocks at once."""
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=32, unique=True)
    location = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.code} — {self.name}"


class LayerFlock(models.Model):
    """One batch of layer birds. Costs accumulate here; eggs/sales too."""
    STATUS = [('ACTIVE', 'Active'), ('CLOSED', 'Closed')]
    farm = models.ForeignKey(LayerFarm, on_delete=models.PROTECT, related_name='flocks')
    name = models.CharField(max_length=80, help_text="e.g. Batch-2026-A")
    placement_date = models.DateField()
    bird_count = models.PositiveIntegerField(help_text="Chicks/birds placed")
    status = models.CharField(max_length=8, choices=STATUS, default='ACTIVE')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-placement_date', '-id']

    def __str__(self):
        return f"{self.name} @ {self.farm.code}"

    # ─── derived figures ───
    @property
    def age_days(self):
        from datetime import date
        return (date.today() - self.placement_date).days

    @property
    def total_mortality(self):
        return self.daily_entries.aggregate(m=models.Sum('mortality'))['m'] or 0

    @property
    def total_culls(self):
        return self.daily_entries.aggregate(c=models.Sum('culls'))['c'] or 0

    @property
    def live_birds(self):
        return self.bird_count - self.total_mortality - self.total_culls

    @property
    def total_cost(self):
        """Everything accumulated against this flock (chicks + feed + med +
        vaccine + overhead). Stored as FlockCost rows."""
        return self.costs.aggregate(t=models.Sum('amount'))['t'] or Decimal('0')

    @property
    def total_eggs(self):
        return self.daily_entries.aggregate(e=models.Sum('eggs'))['e'] or 0

    @property
    def eggs_sold(self):
        agg = self.egg_sales.exclude(voucher__is_reversed=True).aggregate(t=models.Sum('trays'))['t'] or 0
        return agg * 30  # trays -> eggs

    @property
    def egg_stock(self):
        """Eggs on hand = laid - sold (in eggs). Broken handled via daily."""
        broken = self.daily_entries.aggregate(b=models.Sum('broken'))['b'] or 0
        return self.total_eggs - broken - self.eggs_sold

    @property
    def egg_revenue(self):
        return self.egg_sales.exclude(voucher__is_reversed=True).aggregate(t=models.Sum('amount'))['t'] or Decimal('0')


class FlockCost(models.Model):
    """One cost line charged to a flock. The running accumulation that answers
    'this flock has cost ₹N so far'. category keeps it explainable."""
    CATEGORY = [
        ('CHICK', 'Chicks'), ('FEED', 'Feed'), ('MEDICINE', 'Medicine'),
        ('VACCINE', 'Vaccine'), ('PREMIX', 'Premix'), ('LABOUR', 'Labour'),
        ('OVERHEAD', 'Overhead'), ('OTHER', 'Other'),
    ]
    flock = models.ForeignKey(LayerFlock, on_delete=models.CASCADE, related_name='costs')
    date = models.DateField()
    category = models.CharField(max_length=10, choices=CATEGORY)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)
    voucher = models.ForeignKey(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='layer_costs')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.flock.name} {self.category} ₹{self.amount}"


class Purchase(models.Model):
    """Buy an input from a vendor. KIND decides the stock/account.
    RAW/PREMIX/MEDICINE/VACCINE add to their stock item; CHICK is charged
    straight to a flock's cost."""
    KIND = [
        ('RAW', 'Raw Material'), ('PREMIX', 'Premix'),
        ('MEDICINE', 'Medicine'), ('VACCINE', 'Vaccine'), ('CHICK', 'Chicks'),
    ]
    vendor = models.ForeignKey(Party, on_delete=models.PROTECT, related_name='layer_purchases')
    kind = models.CharField(max_length=10, choices=KIND)
    item = models.ForeignKey(Item, on_delete=models.PROTECT, null=True, blank=True, related_name='layer_purchases')
    flock = models.ForeignKey(LayerFlock, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases',
                              help_text="Set for CHICK purchases (charged to this flock)")
    date = models.DateField()
    qty = models.DecimalField(max_digits=14, decimal_places=3, help_text="kg for materials, birds for chicks")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, null=True, blank=True, related_name='layer_purchases')
    rate = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='layer_purchase')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.get_kind_display()} from {self.vendor.name} ₹{self.amount}"


class FeedBatch(models.Model):
    """A feed-mill production batch: consume raw materials/premix -> produce
    feed. Batch cost = materials consumed + overhead; cost_per_kg = that /
    output. Feed produced carries this cost when sent to a flock."""
    date = models.DateField()
    feed_item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='feed_batches')
    output_kg = models.DecimalField(max_digits=14, decimal_places=3)
    materials_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    overhead_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    cost_per_kg = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('0'))
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='layer_feedbatch')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"Feed batch {self.date}: {self.output_kg}kg @ ₹{self.cost_per_kg}/kg"


class FeedBatchInput(models.Model):
    """One raw material consumed in a feed batch."""
    batch = models.ForeignKey(FeedBatch, on_delete=models.CASCADE, related_name='inputs')
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    qty_kg = models.DecimalField(max_digits=14, decimal_places=3)
    cost = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.item.name} {self.qty_kg}kg"


class FeedToFlock(models.Model):
    """Bulk transfer of made feed to a flock, valued at batch cost per kg.
    That rupee value becomes the flock's feed cost."""
    flock = models.ForeignKey(LayerFlock, on_delete=models.PROTECT, related_name='feed_transfers')
    feed_item = models.ForeignKey(Item, on_delete=models.PROTECT)
    date = models.DateField()
    qty_kg = models.DecimalField(max_digits=14, decimal_places=3)
    cost_per_kg = models.DecimalField(max_digits=12, decimal_places=4)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='layer_feedtoflock')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.qty_kg}kg feed -> {self.flock.name}"


class Application(models.Model):
    """Medicine/vaccine/premix administered to a flock (from stock), charged
    to the flock's cost at the item's value."""
    KIND = [('MEDICINE', 'Medicine'), ('VACCINE', 'Vaccine'), ('PREMIX', 'Premix')]
    flock = models.ForeignKey(LayerFlock, on_delete=models.PROTECT, related_name='applications')
    kind = models.CharField(max_length=10, choices=KIND)
    item = models.ForeignKey(Item, on_delete=models.PROTECT, null=True, blank=True)
    date = models.DateField()
    qty = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='layer_application')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.get_kind_display()} -> {self.flock.name} ₹{self.amount}"


class DailyEntry(models.Model):
    """Per-flock production diary: eggs laid, feed consumed, mortality, culls,
    broken eggs. Drives laying %, feed/egg, egg stock."""
    flock = models.ForeignKey(LayerFlock, on_delete=models.CASCADE, related_name='daily_entries')
    date = models.DateField()
    eggs = models.PositiveIntegerField(default=0, help_text="Eggs laid (pieces)")
    broken = models.PositiveIntegerField(default=0)
    feed_kg = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    mortality = models.PositiveIntegerField(default=0)
    culls = models.PositiveIntegerField(default=0)
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        unique_together = ('flock', 'date')

    def __str__(self):
        return f"{self.flock.name} {self.date}: {self.eggs} eggs"


class EggSale(models.Model):
    """Egg sale to a trader, in trays (30 eggs), tagged to a flock.
    A bill: settleable oldest-first like Chicken Center."""
    STATUS = [('PENDING', 'Pending'), ('PARTLY', 'Partly Paid'), ('PAID', 'Paid')]
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name='layer_egg_sales')
    flock = models.ForeignKey(LayerFlock, on_delete=models.PROTECT, related_name='egg_sales')
    date = models.DateField()
    trays = models.DecimalField(max_digits=12, decimal_places=2, help_text="1 tray = 30 eggs")
    rate_per_tray = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount_received = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=8, choices=STATUS, default='PENDING')
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='layer_eggsale')
    whatsapp_status = models.CharField(max_length=20, default='pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"Egg sale {self.date} {self.party.name} {self.trays} trays"

    @property
    def amount_due(self):
        return self.amount - self.amount_received

    def recompute_status(self):
        if self.amount_received <= 0:
            self.status = 'PENDING'
        elif self.amount_received >= self.amount:
            self.status = 'PAID'
        else:
            self.status = 'PARTLY'


class Collection(models.Model):
    """Money received from a trader (settles egg-sale bills oldest-first)."""
    MODE = [('CASH', 'Cash'), ('UPI', 'UPI'), ('BANK', 'Bank')]
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name='layer_collections')
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    advance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    mode = models.CharField(max_length=6, choices=MODE, default='CASH')
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='layer_collection')
    whatsapp_status = models.CharField(max_length=20, default='pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']


class Allocation(models.Model):
    """Links a Collection to the EggSale bills it settled."""
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='allocations')
    egg_sale = models.ForeignKey(EggSale, on_delete=models.PROTECT, related_name='allocations')
    amount = models.DecimalField(max_digits=14, decimal_places=2)


class Payment(models.Model):
    """Money paid to a vendor."""
    MODE = [('CASH', 'Cash'), ('UPI', 'UPI'), ('BANK', 'Bank')]
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name='layer_payments')
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    mode = models.CharField(max_length=6, choices=MODE, default='CASH')
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='layer_payment')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']


class Expense(models.Model):
    """General expense (labour, electricity…). If flock set, charged to that
    flock; else split across active flocks by the service."""
    MODE = [('CASH', 'Cash'), ('UPI', 'UPI'), ('BANK', 'Bank')]
    date = models.DateField()
    account_code = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    mode = models.CharField(max_length=6, choices=MODE, default='CASH')
    split_across_flocks = models.BooleanField(default=True)
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='layer_expense')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
