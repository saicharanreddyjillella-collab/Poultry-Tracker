"""
Shared accounting + inventory core.

This app knows NOTHING about chickens, feed, or eggs. It only understands
universal primitives: accounts, parties, balanced vouchers, units, items and
stock movements. Business modules (chicken_center, feeds, layer) post into it.

Money is ALWAYS DecimalField — never float. Ledger balances are DERIVED from
entries, never stored as a mutable column that can drift.
"""
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


# Which business a record belongs to. Used for filtering/reporting only —
# never for accounting logic. The core treats all businesses identically.
BUSINESS_CHOICES = [
    ('chicken_center', 'Sai Charan Chicken Center'),
    ('feeds', 'Sai Ram Feeds'),
    ('layer', 'Layer Farm'),
    ('common', 'Common / Shared'),
]


# ─────────────────────────────────────────────────────────────
# CHART OF ACCOUNTS
# ─────────────────────────────────────────────────────────────

class Account(models.Model):
    """A line in the chart of accounts. Its type fixes its normal balance
    and where it appears in reports (Balance Sheet vs P&L)."""

    TYPE_CHOICES = [
        ('ASSET', 'Asset'),
        ('LIABILITY', 'Liability'),
        ('INCOME', 'Income'),
        ('EXPENSE', 'Expense'),
        ('EQUITY', 'Equity'),
    ]

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=120)
    type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    # Control accounts group parties (e.g. Debtors groups all customers,
    # Creditors groups all suppliers). Party balances roll up into these.
    is_party_control = models.BooleanField(default=False)
    business = models.CharField(max_length=20, choices=BUSINESS_CHOICES, default='common')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.name}"

    @property
    def is_debit_normal(self):
        """Assets and Expenses increase on the debit side."""
        return self.type in ('ASSET', 'EXPENSE')

    def balance(self, upto=None, business=None):
        """Derived balance = signed sum of all entries hitting this account.
        Returned as a positive number in the account's normal direction."""
        qs = self.entries.all()
        if upto:
            qs = qs.filter(voucher__date__lte=upto)
        if business:
            qs = qs.filter(voucher__business=business)
        agg = qs.aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        debit = agg['d'] or Decimal('0')
        credit = agg['c'] or Decimal('0')
        return (debit - credit) if self.is_debit_normal else (credit - debit)


# ─────────────────────────────────────────────────────────────
# PARTIES (customers / suppliers)
# ─────────────────────────────────────────────────────────────

class Party(models.Model):
    """Anyone you transact with. A party can be both customer and supplier."""

    TYPE_CHOICES = [
        ('CUSTOMER', 'Customer'),
        ('SUPPLIER', 'Supplier'),
        ('BOTH', 'Customer & Supplier'),
    ]

    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    party_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='CUSTOMER')
    # Control account this party rolls into (Debtors / Creditors).
    control_account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='parties')
    business = models.CharField(max_length=20, choices=BUSINESS_CHOICES, default='chicken_center')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Parties'

    def __str__(self):
        return self.name

    def balance(self, upto=None):
        """Positive = party owes us (receivable). Negative = we owe party (payable).
        Derived purely from entries tagged to this party."""
        qs = Entry.objects.filter(party=self)
        if upto:
            qs = qs.filter(voucher__date__lte=upto)
        agg = qs.aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        debit = agg['d'] or Decimal('0')
        credit = agg['c'] or Decimal('0')
        # Debtor-normal: a customer who bought (debit) owes us.
        return debit - credit


# ─────────────────────────────────────────────────────────────
# VOUCHERS + ENTRIES (double-entry)
# ─────────────────────────────────────────────────────────────

class Voucher(models.Model):
    """One business event that groups balanced entries.
    Sum of debits == sum of credits, enforced in the posting service."""

    TYPE_CHOICES = [
        ('SALE', 'Sale'),
        ('PURCHASE', 'Purchase'),
        ('RECEIPT', 'Receipt'),        # money received from a customer
        ('PAYMENT', 'Payment'),        # money paid to a supplier
        ('EXPENSE', 'Expense'),
        ('PRODUCTION', 'Production'),   # feed mill: consume raw, produce finished
        ('SHRINKAGE', 'Shrinkage/Mortality'),
        ('JOURNAL', 'Journal'),
        ('OPENING', 'Opening Balance'),
    ]

    date = models.DateField()
    type = models.CharField(max_length=12, choices=TYPE_CHOICES)
    narration = models.CharField(max_length=300, blank=True)
    business = models.CharField(max_length=20, choices=BUSINESS_CHOICES, default='chicken_center')
    # Trace back to the originating domain record (e.g. chicken_center.Sale #123).
    source_module = models.CharField(max_length=40, blank=True)
    source_ref = models.CharField(max_length=40, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Corrections reverse a voucher rather than editing it.
    is_reversed = models.BooleanField(default=False)
    reverses = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reversed_by')

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.get_type_display()} {self.date} — {self.narration}"

    @property
    def total_debit(self):
        return self.entries.aggregate(t=models.Sum('debit'))['t'] or Decimal('0')

    @property
    def total_credit(self):
        return self.entries.aggregate(t=models.Sum('credit'))['t'] or Decimal('0')

    @property
    def is_balanced(self):
        return self.total_debit == self.total_credit


class Entry(models.Model):
    """A single debit or credit line inside a voucher.
    Exactly one of debit/credit is non-zero."""

    voucher = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='entries')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='entries')
    party = models.ForeignKey(Party, on_delete=models.PROTECT, null=True, blank=True, related_name='entries')
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    def __str__(self):
        side = f"Dr {self.debit}" if self.debit else f"Cr {self.credit}"
        return f"{self.account.code}: {side}"


# ─────────────────────────────────────────────────────────────
# UNITS + ITEMS (generic masters — user-created)
# ─────────────────────────────────────────────────────────────

class Unit(models.Model):
    """A user-created unit of measure. Optional conversion to a base unit
    lets you buy in bags and value in kg (1 bag = 50 kg), etc."""

    name = models.CharField(max_length=40, unique=True)          # e.g. "Kilogram"
    symbol = models.CharField(max_length=12)                     # e.g. "kg", "bag"
    # If this unit converts to a more fundamental one:
    base_unit = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='derived_units')
    factor_to_base = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal('1'),
                                         help_text="1 of this unit = factor_to_base base units (e.g. 1 bag = 50 kg)")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.symbol})"

    def to_base(self, qty):
        """Convert a quantity in this unit to base units."""
        return Decimal(str(qty)) * self.factor_to_base


class Item(models.Model):
    """A user-created tradable/stockable thing. Business-agnostic:
    chicken (kg), feed (bags), raw materials (maize/soya), eggs (trays)."""

    KIND_CHOICES = [
        ('TRADING', 'Trading Good'),       # bought and sold as-is (chicken)
        ('RAW', 'Raw Material'),           # consumed in production (maize, soya)
        ('FINISHED', 'Finished Good'),     # produced in-house (BPSC/BSC/BFP feed)
    ]
    RATE_BASIS_CHOICES = [
        ('PER_KG', 'Per kg'),
        ('PER_UNIT', 'Per unit'),          # per bird, per bag, per tray...
    ]

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='TRADING')
    base_unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='items')
    rate_basis = models.CharField(max_length=10, choices=RATE_BASIS_CHOICES, default='PER_KG')
    business = models.CharField(max_length=20, choices=BUSINESS_CHOICES, default='chicken_center')
    # Accounts this item posts into (optional overrides of business defaults):
    sales_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_items')
    purchase_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_items')
    stock_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_items')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def stock_in_base(self, business=None):
        """Current stock on hand, in the item's base unit.
        = Σ(in) − Σ(out), all movements already stored in base units."""
        qs = self.movements.all()
        if business:
            qs = qs.filter(business=business)
        agg = qs.aggregate(i=models.Sum('qty_in_base'), o=models.Sum('qty_out_base'))
        return (agg['i'] or Decimal('0')) - (agg['o'] or Decimal('0'))


class StockMovement(models.Model):
    """One inventory movement for an item, stored in BASE units so stock
    math is always consistent regardless of the unit used at entry time.

    Movement types: PURCHASE_IN, SALE_OUT, PRODUCE_IN, CONSUME_OUT,
    SHRINKAGE_OUT, ADJUST. Linked to the money voucher when there is one."""

    TYPE_CHOICES = [
        ('PURCHASE_IN', 'Purchase In'),
        ('SALE_OUT', 'Sale Out'),
        ('PRODUCE_IN', 'Produced In'),
        ('CONSUME_OUT', 'Consumed In Production'),
        ('SHRINKAGE_OUT', 'Shrinkage/Mortality Out'),
        ('ADJUST', 'Adjustment'),
    ]

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='movements')
    date = models.DateField()
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    # Stored in base units (converted at entry time). One side is zero.
    qty_in_base = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    qty_out_base = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    # What the user actually typed, kept for display/audit:
    entered_qty = models.DecimalField(max_digits=14, decimal_places=3, default=Decimal('0'))
    entered_unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name='movements')
    business = models.CharField(max_length=20, choices=BUSINESS_CHOICES, default='chicken_center')
    voucher = models.ForeignKey(Voucher, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_movements')
    source_module = models.CharField(max_length=40, blank=True)
    source_ref = models.CharField(max_length=40, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        d = self.qty_in_base or self.qty_out_base
        return f"{self.get_type_display()} {self.item.name} {d}"


# ─────────────────────────────────────────────────────────────
# AUDIT
# ─────────────────────────────────────────────────────────────

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('EDIT', 'Edit'),
        ('DELETE', 'Delete'),
        ('REVERSE', 'Reverse'),
    ]
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    object_type = models.CharField(max_length=60)
    object_id = models.CharField(max_length=40)
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} {self.object_type}#{self.object_id} by {self.user}"
