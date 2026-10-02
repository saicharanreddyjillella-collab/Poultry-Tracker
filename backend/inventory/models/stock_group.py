from django.db import models
from accounting.models import BUSINESS_CHOICES


class StockGroup(models.Model):
    """Tally-style stock group tree. Every stock item belongs to a group.
    One 'Primary' group per business is created automatically; all other
    groups nest under it (unlimited depth)."""

    name = models.CharField(max_length=120)
    under = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True,
                              related_name='children',
                              help_text="Parent group. Null only for the business's Primary group.")
    business = models.CharField(max_length=20, choices=BUSINESS_CHOICES, default='layer')
    is_primary = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ('name', 'business')

    def __str__(self):
        return f"{self.name} ({self.business})"

    @property
    def path(self):
        """Full path like 'Primary › Raw Materials › Grains'."""
        parts = [self.name]
        node = self.under
        seen = {self.id}
        while node and node.id not in seen:
            parts.append(node.name)
            seen.add(node.id)
            node = node.under
        return ' › '.join(reversed(parts))

    @classmethod
    def primary_for(cls, business):
        """Get or create the Primary group for a business."""
        grp, _ = cls.objects.get_or_create(
            business=business, is_primary=True,
            defaults={'name': 'Primary', 'under': None})
        return grp
