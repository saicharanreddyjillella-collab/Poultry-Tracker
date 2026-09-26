from decimal import Decimal
from django.db import models
from accounting.models import Voucher, BUSINESS_CHOICES
from .unit import Unit
from .item import Item


class StockMovement(models.Model):
    """One inventory movement for an item, stored in BASE units so stock math
    is always consistent regardless of the unit used at entry time. Linked to
    the money voucher when there is one."""

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
