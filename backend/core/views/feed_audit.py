"""Feed leakage detector: supervisors' bag counts + the admin Feed Audit report."""
import datetime

from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..access import NotPlant, is_admin, visible_farm_ids, visible_farms
from ..feed_audit import CLOSED_LOOKBACK_DAYS, book_stock_for, run_audit
from ..features import feature_required
from ..models import Flock, FeedStockCount
from ..serializers import FeedBagsField
from ..pagination import GuardedListMixin
from ..permissions import CanEditFlockData, IsAdmin


class FeedStockCountSerializer(serializers.ModelSerializer):
    counted_by_name = serializers.SerializerMethodField()
    book = serializers.SerializerMethodField()
    bags = FeedBagsField()
    gap_bags = serializers.SerializerMethodField()

    class Meta:
        model = FeedStockCount
        fields = ['id', 'flock', 'date', 'bags', 'notes',
                  'counted_by', 'counted_by_name', 'created_at', 'book', 'gap_bags']
        read_only_fields = ['counted_by', 'created_at']
        validators = []          # duplicate day → a readable message below, not a raw constraint error

    def get_counted_by_name(self, obj):
        u = obj.counted_by
        return (u.get_full_name() or u.username) if u else ''

    def _book(self, obj):
        cache = self.context.setdefault('_book', {})
        if obj.pk not in cache:
            b = book_stock_for(obj.flock, obj.date)
            cache[obj.pk] = {k: v for k, v in b.items() if k != 'received'}
        return cache[obj.pk]

    def get_book(self, obj):
        return self._book(obj)

    def get_gap_bags(self, obj):
        """Paper minus counted: positive = bags missing at the farm."""
        return self._book(obj)['total'] - sum((obj.bags or {}).values())

    def validate(self, attrs):
        flock = attrs.get('flock') or self.instance.flock
        day = attrs.get('date') or self.instance.date
        if day > timezone.localdate():
            raise ValidationError({'date': 'A bag count cannot be in the future.'})
        if day < flock.placement_date:
            raise ValidationError({'date': f'Date cannot be before placement ({flock.placement_date}).'})
        if self.instance is None and flock.status != 'active':
            raise ValidationError({'flock': 'Bag counts can only be added while the flock is active.'})
        dup = FeedStockCount.objects.filter(flock=flock, date=day)
        if self.instance:
            dup = dup.exclude(pk=self.instance.pk)
        if dup.exists():
            raise ValidationError({'date': f'A bag count for {day:%d %b %Y} already exists for this flock.'})
        return attrs


class FeedStockCountViewSet(GuardedListMixin, viewsets.ModelViewSet):
    """Supervisors record counts for flocks in their regions; only an admin can
    change or delete a count (it is evidence for the feed audit)."""
    queryset = FeedStockCount.objects.select_related('flock', 'flock__farm', 'counted_by').all()
    serializer_class = FeedStockCountSerializer
    permission_classes = [IsAuthenticated, NotPlant, feature_required('feed_audit'), CanEditFlockData]

    def get_queryset(self):
        qs = super().get_queryset().filter(flock__farm_id__in=visible_farm_ids(self.request.user))
        flock_id = self.request.query_params.get('flock')
        if flock_id:
            qs = qs.filter(flock_id=flock_id)
        return qs

    def perform_create(self, serializer):
        flock = serializer.validated_data['flock']
        if not Flock.objects.filter(pk=flock.pk, farm__in=visible_farms(self.request.user)).exists():
            raise PermissionDenied('This flock is outside your regions.')
        from ..billlock import assert_flock_unlocked
        assert_flock_unlocked(flock)
        serializer.save(counted_by=self.request.user)

    def _admin_only(self):
        if not is_admin(self.request.user):
            raise PermissionDenied('Only an admin can change or remove a bag count.')

    def perform_update(self, serializer):
        self._admin_only()
        serializer.save()

    def perform_destroy(self, instance):
        self._admin_only()
        instance.delete()


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin, feature_required('feed_audit')])   # admin only
def feed_audit_report(request):
    """Active flocks and flocks closed in the last CLOSED_LOOKBACK_DAYS days.
    ?region=… narrows to one region."""
    today = timezone.localdate()
    since = today - datetime.timedelta(days=CLOSED_LOOKBACK_DAYS)
    flocks = Flock.objects.select_related('farm').filter(status__in=('active', 'closed'))
    flocks = flocks.exclude(status='closed', daily_entries__isnull=True)
    recent_closed = Flock.objects.filter(status='closed', daily_entries__date__gte=since).values('id')
    from django.db.models import Q
    flocks = flocks.filter(Q(status='active') | Q(id__in=recent_closed)).distinct()
    region = request.query_params.get('region')
    if region:
        flocks = flocks.filter(farm__region=region)
    return Response(run_audit(flocks, today))
