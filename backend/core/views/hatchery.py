"""Chick quality by hatchery: the hatchery list + the admin comparison report."""
import datetime

from django.db.models import F, ProtectedError, Q, Sum
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response

from ..access import NotPlant, is_admin
from ..models import BillConfig, Flock, Hatchery
from ..permissions import IsAdmin

FIRST_WEEK_DAYS = 7
WORSE_THAN_AVERAGE_PTS = 0.5      # first-week mortality this many points above the average → flagged


class HatcherySerializer(serializers.ModelSerializer):
    class Meta:
        model = Hatchery
        fields = ['id', 'name', 'active', 'notes']

    def validate_name(self, value):
        value = value.strip()
        dup = Hatchery.objects.filter(name__iexact=value)
        if self.instance:
            dup = dup.exclude(pk=self.instance.pk)
        if dup.exists():
            raise ValidationError(f'{value} is already in the list.')
        return value


class HatcheryViewSet(viewsets.ModelViewSet):
    """Everyone (except the feed mill) can read the list; only an admin changes it."""
    queryset = Hatchery.objects.all()
    serializer_class = HatcherySerializer
    permission_classes = [IsAuthenticated, NotPlant]
    pagination_class = None

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in SAFE_METHODS and not is_admin(request.user):
            raise PermissionDenied('Only an admin can change the hatchery list.')

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError({'detail': f'{instance.name} has flocks, so it can\'t be removed. '
                                             f'Mark it as not used instead.'})


def _pct(part, whole):
    return round(part / whole * 100, 2) if whole else None


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])   # business-sensitive: admin only
def hatchery_report(request):
    """Flocks placed in the last ?days= (default 180), compared by hatchery.
    First-week mortality only counts flocks at least 7 days old (complete first week)."""
    try:
        days = max(7, min(int(request.query_params.get('days', 180)), 730))
    except ValueError:
        days = 180
    today = timezone.localdate()
    since = today - datetime.timedelta(days=days)
    live = Q(daily_entries__deleted_at__isnull=True)
    first_week = live & Q(daily_entries__date__lte=F('placement_date') + datetime.timedelta(days=FIRST_WEEK_DAYS))
    flocks = (Flock.objects.filter(placement_date__gte=since).select_related('farm', 'hatchery')
              .annotate(week1_mort=Sum('daily_entries__mortality_count', filter=first_week),
                        total_mort=Sum('daily_entries__mortality_count', filter=live))
              .order_by('-placement_date'))
    limit = float(BillConfig.get_active().first_week_mortality_limit_pct)

    groups = {}
    for f in flocks:
        key = f.hatchery_id or 0
        g = groups.setdefault(key, {'hatchery_id': f.hatchery_id,
                                    'name': f.hatchery.name if f.hatchery else 'Not recorded',
                                    'active': f.hatchery.active if f.hatchery else None, 'flocks': []})
        complete = (today - f.placement_date).days >= FIRST_WEEK_DAYS
        w1 = _pct(f.week1_mort or 0, f.chick_count) if complete else None
        g['flocks'].append({
            'flock_id': f.id, 'farm_name': f.farm.name, 'farm_code': f.farm.farm_code, 'region': f.farm.region,
            'placement_date': f.placement_date.isoformat(), 'status': f.status, 'chicks': f.chick_count,
            'doa': f.doa_count, 'doa_pct': _pct(f.doa_count, f.chick_count),
            'chick_weight_g': float(f.chick_weight_g) if f.chick_weight_g is not None else None,
            'week1_mortality': (f.week1_mort or 0) if complete else None, 'week1_pct': w1,
            'over_limit': w1 is not None and w1 > limit,
            'final_mortality_pct': _pct(f.total_mort or 0, f.chick_count) if f.status == 'closed' else None,
        })

    def summarise(g):
        fl = g['flocks']
        chicks = sum(x['chicks'] for x in fl)
        done = [x for x in fl if x['week1_pct'] is not None]
        weights = [x['chick_weight_g'] for x in fl if x['chick_weight_g'] is not None]
        closed = [x for x in fl if x['final_mortality_pct'] is not None]
        return {
            'flocks_count': len(fl), 'chicks': chicks,
            'doa': sum(x['doa'] for x in fl), 'doa_pct': _pct(sum(x['doa'] for x in fl), chicks),
            'avg_chick_weight_g': round(sum(weights) / len(weights), 1) if weights else None,
            'weighed_flocks': len(weights),
            'week1_pct': _pct(sum(x['week1_mortality'] for x in done), sum(x['chicks'] for x in done)),
            'week1_flocks': len(done),
            'over_limit_flocks': sum(1 for x in done if x['over_limit']),
            'final_mortality_pct': _pct(sum(x['final_mortality_pct'] * x['chicks'] for x in closed) / 100,
                                        sum(x['chicks'] for x in closed)) if closed else None,
        }

    rows = [{**{k: v for k, v in g.items() if k != 'flocks'}, **summarise(g), 'flocks': g['flocks']}
            for g in groups.values()]
    overall = summarise({'flocks': [x for g in groups.values() for x in g['flocks']]})
    avg = overall['week1_pct']
    for r in rows:
        w = r['week1_pct']
        if w is None:
            r['verdict'], r['verdict_level'] = 'No flock past its first week yet.', None
        elif w > limit:
            r['verdict'], r['verdict_level'] = (f'First-week mortality {w}% is above your {limit:g}% limit.', 'high')
        elif avg is not None and w > avg + WORSE_THAN_AVERAGE_PTS:
            r['verdict'], r['verdict_level'] = (f'First-week mortality {w}% is worse than the average {avg}%.',
                                                'medium')
        else:
            r['verdict'], r['verdict_level'] = 'Within limits.', 'ok'
    order = {'high': 0, 'medium': 1, 'ok': 2, None: 3}
    rows.sort(key=lambda r: (r['hatchery_id'] is None, order[r['verdict_level']], -(r['week1_pct'] or 0)))
    return Response({'as_of': today.isoformat(), 'days': days, 'since': since.isoformat(),
                     'first_week_limit_pct': limit, 'overall': overall, 'hatcheries': rows})
