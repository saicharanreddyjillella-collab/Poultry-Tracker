"""Company costs are for the admin only.

Removes these fields from every API response for anyone who is not an admin
(supervisors; the feed mill never reaches these screens anyway). Done in one
place so every screen — and any future one — follows the same rule.

Kept for supervisors: their own entries (sale rates/amounts, medicine costs),
birds, feed, weights, FCR, and what the grower is paid (growing charges,
incentive, recoveries, TDS, net payable).
"""
HIDDEN_FIELDS = frozenset({
    # bill: the company's cost of production
    'chick_cost', 'feed_cost', 'medicine_cost', 'admin_cost',
    'production_cost_total', 'production_cost_per_kg', 'config_snapshot',
    'avg_selling_price',
    # reports / dashboard: prices, sale totals, cost per kg
    'feed_rates', 'latest_feed_rates', 'total_feed_cost', 'total_sale_amount',
    'cost_per_kg_production', 'cost_per_kg',
    # grower's tax id (TDS is the admin's job)
    'pan',
})


def _is_admin(user):
    if user is None or not user.is_authenticated:
        return True                      # nothing to show anyway; leave errors untouched
    profile = getattr(user, 'profile', None)
    return profile.is_admin if profile is not None else user.is_superuser


def redact(data):
    if isinstance(data, dict):
        return {k: redact(v) for k, v in data.items() if k not in HIDDEN_FIELDS}
    if isinstance(data, list):
        return [redact(x) for x in data]
    return data


class HideCompanyCostsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_template_response(self, request, response):
        # DRF responses are rendered after this hook, so response.data can still be changed.
        # request.user is set by DRF's authentication (JWT) during the view.
        if hasattr(response, 'data') and request.path.startswith('/api/') and not _is_admin(request.user):
            response.data = redact(response.data)
        return response
