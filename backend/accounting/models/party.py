from decimal import Decimal
from django.db import models
from .account import Account, BUSINESS_CHOICES


class Party(models.Model):
    """Anyone you transact with. A party can be both customer and supplier."""

    TYPE_CHOICES = [
        ('CUSTOMER', 'Customer'),
        ('SUPPLIER', 'Supplier'),
        ('BOTH', 'Customer & Supplier'),
    ]

    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    state = models.CharField(max_length=80, blank=True)
    gst_number = models.CharField(max_length=20, blank=True)
    pan = models.CharField(max_length=15, blank=True)
    party_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='BOTH')
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
        """Positive = party owes us (receivable). Negative = we owe them
        (payable). Derived purely from entries tagged to this party."""
        from .voucher import Entry
        qs = Entry.objects.filter(party=self)
        if upto:
            qs = qs.filter(voucher__date__lte=upto)
        agg = qs.aggregate(d=models.Sum('debit'), c=models.Sum('credit'))
        debit = agg['d'] or Decimal('0')
        credit = agg['c'] or Decimal('0')
        return debit - credit
