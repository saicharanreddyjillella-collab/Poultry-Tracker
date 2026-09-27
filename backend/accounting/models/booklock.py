from django.db import models
from django.contrib.auth.models import User
from .account import BUSINESS_CHOICES


class BookLock(models.Model):
    """Freezes the books up to and including closed_through for a business.
    No voucher may be posted or reversed with a date <= closed_through.
    One row per business; an admin moves the date forward to close more days,
    or back to re-open (both logged in AuditLog)."""
    business = models.CharField(max_length=20, choices=BUSINESS_CHOICES, unique=True)
    closed_through = models.DateField(null=True, blank=True,
                                      help_text="Books are locked on/before this date")
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business} locked through {self.closed_through or '—'}"

    @classmethod
    def closed_date_for(cls, business):
        row = cls.objects.filter(business=business).first()
        return row.closed_through if row else None
