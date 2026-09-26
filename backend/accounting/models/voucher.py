from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from .account import Account, BUSINESS_CHOICES
from .party import Party


class Voucher(models.Model):
    """One business event grouping balanced entries.
    Sum of debits == sum of credits, enforced by the posting service."""

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
