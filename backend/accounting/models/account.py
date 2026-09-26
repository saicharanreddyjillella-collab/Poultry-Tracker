from decimal import Decimal
from django.db import models

# Which business a record belongs to — for filtering/reporting only, never
# for accounting logic. The core treats all businesses identically.
BUSINESS_CHOICES = [
    ('chicken_center', 'Sai Charan Chicken Center'),
    ('feeds', 'Sai Ram Feeds'),
    ('layer', 'Layer Farm'),
    ('common', 'Common / Shared'),
]


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
    # Control accounts group parties (Debtors groups customers, Creditors
    # groups suppliers). Party balances roll up into these.
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
        """Derived balance = signed sum of entries, returned positive in the
        account's normal direction."""
        qs = self.entries.all()
        if upto:
            qs = qs.filter(voucher__date__lte=upto)
        if business:
            qs = qs.filter(voucher__business=business)
        agg = qs.aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        debit = agg['d'] or Decimal('0')
        credit = agg['c'] or Decimal('0')
        return (debit - credit) if self.is_debit_normal else (credit - debit)
