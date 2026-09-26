from decimal import Decimal
from django.db import models


class Unit(models.Model):
    """A user-created unit of measure. Optional conversion to a base unit lets
    you buy in bags and value in kg (1 bag = 50 kg), etc."""

    name = models.CharField(max_length=40, unique=True)          # "Kilogram"
    symbol = models.CharField(max_length=12)                     # "kg", "bag"
    base_unit = models.ForeignKey('self', on_delete=models.SET_NULL, null=True,
                                  blank=True, related_name='derived_units')
    factor_to_base = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal('1'),
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
