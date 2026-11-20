"""E4: automatic audit trail on money-affecting records."""
import datetime
from decimal import Decimal

import pytest

from core.models import AuditLog, Farm, Sale, FeedRate

pytestmark = pytest.mark.django_db


class TestAuditSignals:
    def test_create_recorded(self, farm):
        rows = AuditLog.objects.filter(model='Farm', object_id=str(farm.id))
        assert rows.filter(action='create').count() == 1
        snap = rows.get(action='create').changes
        assert snap['farm_code'] == 'F001'

    def test_update_records_only_changed_fields(self, farm):
        farm.name = 'Renamed Farm'
        farm.save()
        row = AuditLog.objects.get(model='Farm', object_id=str(farm.id), action='update')
        assert row.changes == {'name': ['Test Farm', 'Renamed Farm']}

    def test_noop_save_records_nothing(self, farm):
        before = AuditLog.objects.filter(action='update').count()
        farm.save()  # no field changed
        assert AuditLog.objects.filter(action='update').count() == before

    def test_delete_recorded_with_snapshot(self, farm):
        fid = farm.id
        farm.delete()
        row = AuditLog.objects.get(model='Farm', object_id=str(fid), action='delete')
        assert row.changes['farm_code'] == 'F001'

    def test_decimal_and_date_are_json_safe(self, farm, make_flock):
        f = make_flock(farm, status='active')
        s = Sale.objects.create(flock=f, date=f.placement_date, bird_count=10,
                                total_weight_kg=Decimal('20.50'))
        row = AuditLog.objects.get(model='Sale', object_id=str(s.id), action='create')
        assert row.changes['total_weight_kg'] == '20.50'
        assert row.changes['date'] == f.placement_date.isoformat()
        assert row.changes['flock'] == f.id  # FK stored as id

    def test_unaudited_model_ignored(self, db):
        FeedRate.objects.create(week_start_date=datetime.date.today(), feed_type='BFP',
                                rate_per_kg=Decimal('44'))
        assert AuditLog.objects.filter(model='FeedRate').count() == 0

    def test_system_action_has_no_actor(self, farm):
        row = AuditLog.objects.get(model='Farm', object_id=str(farm.id), action='create')
        assert row.actor is None and row.actor_username == ''


class TestAuditActor:
    def test_api_change_captures_jwt_user(self, auth_admin, admin_user, farm):
        resp = auth_admin.patch(f'/api/farms/{farm.id}/', {'location': 'Shed-9'}, format='json')
        assert resp.status_code in (200, 202)
        row = AuditLog.objects.filter(model='Farm', object_id=str(farm.id), action='update').first()
        assert row is not None
        assert row.actor_id == admin_user.id
        assert row.actor_username == 'admin'
        assert row.changes == {'location': ['', 'Shed-9']}

    def test_bill_generation_audited(self, auth_admin, farm, make_flock, config):
        from core.models import DailyEntry
        f = make_flock(farm, chicks=1000, status='active', placed_days_ago=42)
        DailyEntry.objects.create(flock=f, date=f.placement_date + datetime.timedelta(days=1),
                                  feed_bags={'BFP': 40})
        Sale.objects.create(flock=f, date=f.placement_date, bird_count=1000,
                            total_weight_kg=Decimal('2000'), rate_per_kg=Decimal('100'))
        resp = auth_admin.post(f'/api/flocks/{f.id}/close-and-bill/', {}, format='json')
        assert resp.status_code in (200, 201), resp.data
        assert AuditLog.objects.filter(model='Bill', action='create', actor_username='admin').exists()


class TestAuditApi:
    def test_admin_can_read_and_filter(self, auth_admin, farm):
        farm.name = 'X'; farm.save()
        resp = auth_admin.get(f'/api/audit-log/?model=Farm&object_id={farm.id}')
        assert resp.status_code == 200
        actions = {r['action'] for r in resp.data}
        assert actions == {'create', 'update'}

    def test_non_admin_forbidden(self, api, supervisor_user):
        r = api.post('/api/auth/login/', {'username': 'sup', 'password': 'pass12345'}, format='json')
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        assert api.get('/api/audit-log/').status_code == 403

    def test_read_only(self, auth_admin):
        assert auth_admin.post('/api/audit-log/', {}, format='json').status_code == 405
