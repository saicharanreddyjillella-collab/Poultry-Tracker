"""E13 — API pagination that doesn't break existing screens.

OptionalPageNumberPagination (the project default):
  * no ?page / ?page_size  → full list, plain JSON array (unchanged behaviour)
  * ?page=N[&page_size=M]  → {"count", "next", "previous", "results"}
    page_size defaults to 50, capped at 500.

GuardedListMixin, for high-volume endpoints: a list request that names none of
`list_filters` (e.g. ?flock=) is ALWAYS paginated, so "give me every daily
entry ever" can't run away; filtered requests behave as before.
"""
from rest_framework.pagination import PageNumberPagination


class OptionalPageNumberPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500

    def paginate_queryset(self, queryset, request, view=None, force=False):
        params = request.query_params
        if not force and self.page_query_param not in params and self.page_size_query_param not in params:
            return None
        # Stable pages need a deterministic order.
        if hasattr(queryset, 'ordered') and not queryset.ordered:
            queryset = queryset.order_by('pk')
        return super().paginate_queryset(queryset, request, view)


class GuardedListMixin:
    list_filters = ('flock',)

    def paginate_queryset(self, queryset):
        if self.paginator is None:
            return None
        has_filter = any(self.request.query_params.get(f) for f in self.list_filters)
        if isinstance(self.paginator, OptionalPageNumberPagination):
            return self.paginator.paginate_queryset(queryset, self.request, view=self, force=not has_filter)
        return self.paginator.paginate_queryset(queryset, self.request, view=self)
