from decimal import Decimal
from django.db import models
from accounting.models import Account, BUSINESS_CHOICES
from .unit import Unit
from .stock_group import StockGroup


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
    stock_group = models.ForeignKey(StockGroup, on_delete=models.PROTECT, null=True, blank=True, related_name='items')
    rate_basis = models.CharField(max_length=10, choices=RATE_BASIS_CHOICES, default='PER_KG')
    business = models.CharField(max_length=20, choices=BUSINESS_CHOICES, default='chicken_center')
    # Optional per-item account overrides (else business defaults are used):
    sales_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_items')
    purchase_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_items')
    stock_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_items')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def stock_on_hand(self, business=None):
        """Current stock in the item's base unit = Σ(in) − Σ(out)."""
        qs = self.movements.all()
        if business:
            qs = qs.filter(business=business)
        agg = qs.aggregate(i=models.Sum('qty_in_base'), o=models.Sum('qty_out_base'))
        return (agg['i'] or Decimal('0')) - (agg['o'] or Decimal('0'))
