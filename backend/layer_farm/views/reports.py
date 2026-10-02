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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def flock_production(request, flock_id):
    """Daily production analytics for a flock: per-day laying %, feed per egg,
    cumulative eggs, plus period totals. Drives the production curve."""
    from datetime import date as date_cls
    f = LayerFlock.objects.get(id=flock_id)
    entries = f.daily_entries.order_by('date')

    rows = []
    cum_eggs = 0
    cum_feed = Decimal('0')
    cum_mort = 0
    cum_culls = 0
    birds = f.bird_count
    for e in entries:
        # live birds on that day = placed - mortality/culls so far (incl today)
        cum_mort += e.mortality
        cum_culls += e.culls
        live_today = birds - cum_mort - cum_culls
        cum_eggs += e.eggs
        cum_feed += e.feed_kg
        day_num = (e.date - f.placement_date).days
        laying_pct = round((e.eggs / live_today) * 100, 1) if live_today > 0 else 0
        feed_per_egg = round(float(e.feed_kg) * 1000 / e.eggs, 1) if e.eggs > 0 else None  # grams/egg
        rows.append({
            'date': str(e.date), 'day': day_num,
            'eggs': e.eggs, 'broken': e.broken, 'feed_kg': float(e.feed_kg),
            'mortality': e.mortality, 'culls': e.culls,
            'live_birds': live_today, 'laying_pct': laying_pct,
            'feed_per_egg_g': feed_per_egg, 'cumulative_eggs': cum_eggs,
        })

    total_eggs = cum_eggs
    total_feed = cum_feed
    avg_lay = round(sum(r['laying_pct'] for r in rows) / len(rows), 1) if rows else 0
    feed_per_egg = round(float(total_feed) * 1000 / total_eggs, 1) if total_eggs > 0 else None

    return Response({
        'flock_id': f.id, 'flock_name': f.name,
        'rows': rows,
        'total_eggs': total_eggs, 'total_feed_kg': float(total_feed),
        'avg_laying_pct': avg_lay, 'feed_per_egg_g': feed_per_egg,
        'peak_laying_pct': max((r['laying_pct'] for r in rows), default=0),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feed_stock(request):
    """Feed on hand per finished-feed item = produced - sent to flocks."""
    from django.db.models import Sum
    from inventory.models import Item
    from ..models import FeedBatch, FeedToFlock
    rows = []
    for it in Item.objects.filter(business='layer', kind='FINISHED', active=True):
        produced = FeedBatch.objects.filter(feed_item=it).exclude(voucher__is_reversed=True).aggregate(t=Sum('output_kg'))['t'] or Decimal('0')
        sent = FeedToFlock.objects.filter(feed_item=it).exclude(voucher__is_reversed=True).aggregate(t=Sum('qty_kg'))['t'] or Decimal('0')
        rows.append({'item_id': it.id, 'name': it.name,
                     'produced_kg': float(produced), 'sent_kg': float(sent),
                     'on_hand_kg': float(produced - sent)})
    return Response({'rows': rows})
