"""
Chicken Center domain models — the business-facing records for the live-bird
trading operation. Each transactional record links to the accounting Voucher
that the service posts, so money and stock stay in the shared core while the
domain keeps its own readable fields (customer, weight, rate…).

BUSINESS = 'chicken_center' everywhere here.
"""
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from accounting.models import Party, Voucher
from inventory.models import Item, Unit

BUSINESS = 'chicken_center'


class Sale(models.Model):
    """A sale of chicken (kg) to a shop customer, priced per kg.
    Also a BILL: it can be settled by collections oldest-first."""
    STATUS_CHOICES = [('PENDING', 'Pending'), ('PARTLY', 'Partly Paid'), ('PAID', 'Paid')]
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name='cc_sales')
    # Header-level item/weight/rate are used for single-item sales. Multi-item
    # sales leave these null and carry SaleLine children instead. `amount` is
    # always the bill total either way.
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='cc_sales', null=True, blank=True)
    date = models.DateField()
    weight_kg = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    rate_per_kg = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount_received = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default='PENDING')
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='cc_sale')
    whatsapp_status = models.CharField(max_length=20, default='pending')  # pending/sent/failed/disabled
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"Sale {self.date} {self.party.name} ₹{self.amount}"

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


class Purchase(models.Model):
    """A purchase of chicken (kg) from a supplier."""
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name='cc_purchases')
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='cc_purchases')
    date = models.DateField()
    weight_kg = models.DecimalField(max_digits=12, decimal_places=3)
    rate_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='cc_purchase')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"Purchase {self.date} {self.party.name} ₹{self.amount}"


class Collection(models.Model):
    """Money received from a customer."""
    MODE_CHOICES = [('CASH', 'Cash'), ('UPI', 'UPI'), ('BANK', 'Bank')]
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name='cc_collections')
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    advance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                  help_text="Part of this receipt not applied to any bill (held as credit)")
    mode = models.CharField(max_length=6, choices=MODE_CHOICES, default='CASH')
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='cc_collection')
    whatsapp_status = models.CharField(max_length=20, default='pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"Collection {self.date} {self.party.name} ₹{self.amount}"


class Payment(models.Model):
    """Money paid to a supplier."""
    MODE_CHOICES = [('CASH', 'Cash'), ('UPI', 'UPI'), ('BANK', 'Bank')]
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name='cc_payments')
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    mode = models.CharField(max_length=6, choices=MODE_CHOICES, default='CASH')
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='cc_payment')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"Payment {self.date} {self.party.name} ₹{self.amount}"


class Expense(models.Model):
    """A running expense (fuel, wood, covers, food, stationery…).
    account is the expense head (accounting.Account code)."""
    MODE_CHOICES = [('CASH', 'Cash'), ('UPI', 'UPI'), ('BANK', 'Bank')]
    date = models.DateField()
    account_code = models.CharField(max_length=32)  # e.g. FUEL, WOOD, COVERS
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    mode = models.CharField(max_length=6, choices=MODE_CHOICES, default='CASH')
    note = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='cc_expense')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"Expense {self.date} {self.account_code} ₹{self.amount}"


class Shrinkage(models.Model):
    """Weight lost / birds dead before sale — reduces stock, books a loss."""
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='cc_shrinkage')
    date = models.DateField()
    weight_kg = models.DecimalField(max_digits=12, decimal_places=3)
    # Value booked as loss = weight × valuation rate (last purchase rate or manual)
    value = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    reason = models.CharField(max_length=200, blank=True)
    voucher = models.OneToOneField(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='cc_shrinkage')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"Shrinkage {self.date} {self.item.name} {self.weight_kg}kg"


class Allocation(models.Model):
    """Links a Collection to the Sale (bill) it settled, and how much.
    A receipt of ₹25,000 across a ₹15,000 and ₹20,000 bill produces two
    allocations: 15,000 → bill#1 (paid), 10,000 → bill#2 (partly)."""
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='allocations')
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='allocations')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"₹{self.amount} of receipt #{self.collection_id} → bill #{self.sale_id}"


class SaleLine(models.Model):
    """One item line on a sale bill. A single-item sale has one line;
    a multi-item sale has several. weight*rate = amount."""
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='lines')
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='cc_sale_lines')
    weight_kg = models.DecimalField(max_digits=12, decimal_places=3)
    rate_per_kg = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.item.name} {self.weight_kg}kg @ {self.rate_per_kg}"
