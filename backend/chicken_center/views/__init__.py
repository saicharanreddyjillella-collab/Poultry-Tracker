# Re-export all views so urls.py keeps importing from chicken_center.views
from .transactions import (
    sales, purchases, collections, payments, expenses, shrinkage,
    reverse_entry, opening_party, opening_cash,
)
from .reports import (
    pending_bills, compute_ageing, ageing, sale_detail, daybook, sales_summary,
)

__all__ = [
    'sales', 'purchases', 'collections', 'payments', 'expenses', 'shrinkage',
    'reverse_entry', 'opening_party', 'opening_cash',
    'pending_bills', 'compute_ageing', 'ageing', 'sale_detail', 'daybook',
    'sales_summary',
]
