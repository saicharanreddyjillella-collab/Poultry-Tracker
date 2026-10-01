from decimal import Decimal
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import LayerFlock, FlockCost


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def flock_summary(request, flock_id):
    """The headline per-flock picture: cost accumulated (by category) vs egg
    output + revenue, and where the flock stands."""
    f = LayerFlock.objects.select_related('farm').get(id=flock_id)

    # Cost by category
    by_cat = {}
    for c in f.costs.all():
        by_cat[c.category] = by_cat.get(c.category, Decimal('0')) + c.amount
    cost_lines = [{'category': k, 'amount': v} for k, v in sorted(by_cat.items(), key=lambda x: -x[1])]

    total_cost = f.total_cost
    revenue = f.egg_revenue
    total_eggs = f.total_eggs
    live = f.live_birds
    laying_pct = round((total_eggs / (live * max(1, f.age_days))) * 100, 1) if live > 0 and f.age_days > 0 else 0
    cost_per_egg = round(float(total_cost) / total_eggs, 2) if total_eggs > 0 else None

    return Response({
        'flock_id': f.id, 'flock_name': f.name, 'farm_name': f.farm.name,
        'placement_date': f.placement_date, 'age_days': f.age_days,
        'bird_count': f.bird_count, 'live_birds': live,
        'total_mortality': f.total_mortality, 'total_culls': f.total_culls,
        'cost_lines': cost_lines, 'total_cost': total_cost,
        'total_eggs': total_eggs, 'eggs_sold': f.eggs_sold,
        'egg_stock': f.egg_stock, 'egg_revenue': revenue,
        'net_position': revenue - total_cost,
        'cost_per_egg': cost_per_egg,
        'status': f.status,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    """Overview across all layer flocks."""
    flocks = LayerFlock.objects.select_related('farm').all()
    rows = []
    tot_cost = tot_rev = Decimal('0')
    tot_birds = 0
    for f in flocks:
        rows.append({
            'flock_id': f.id, 'flock_name': f.name, 'farm_name': f.farm.name,
            'status': f.status, 'age_days': f.age_days, 'live_birds': f.live_birds,
            'total_cost': f.total_cost, 'egg_revenue': f.egg_revenue,
            'net_position': f.egg_revenue - f.total_cost,
            'egg_stock': f.egg_stock,
        })
        tot_cost += f.total_cost
        tot_rev += f.egg_revenue
        if f.status == 'ACTIVE':
            tot_birds += f.live_birds
    return Response({
        'flocks': rows,
        'total_cost': tot_cost, 'total_revenue': tot_rev,
        'net_position': tot_rev - tot_cost, 'active_birds': tot_birds,
    })
