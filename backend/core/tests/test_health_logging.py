"""E6/E8: health endpoint + logging config."""
from unittest import mock

import pytest
from django.conf import settings

pytestmark = pytest.mark.django_db


class TestHealth:
    def test_ok_unauthenticated(self, api):
        resp = api.get('/api/health/')
        assert resp.status_code == 200
        assert resp.data == {'status': 'ok', 'db': 'ok'}

    def test_503_when_db_down(self, api):
        with mock.patch('core.views.health.connection') as conn:
            conn.cursor.side_effect = Exception('db gone')
            resp = api.get('/api/health/')
        assert resp.status_code == 503
        assert resp.data['status'] == 'degraded'
        assert resp.data['db'] == 'error'

    def test_not_throttled(self, api):
        # well past the 10/min login throttle; health must never 429
        codes = {api.get('/api/health/').status_code for _ in range(15)}
        assert codes == {200}

    def test_reveals_nothing_sensitive(self, api):
        body = str(api.get('/api/health/').data)
        for secret in ('SECRET', 'postgres', settings.SECRET_KEY):
            assert secret not in body


class TestLoggingConfig:
    def test_logging_configured(self):
        assert settings.LOGGING['version'] == 1
        assert 'console' in settings.LOGGING['handlers']
        assert 'core' in settings.LOGGING['loggers']

    def test_root_level_from_env_default(self):
        # tests run with DEBUG=True -> default DEBUG level
        assert settings.LOGGING['root']['level'] == settings.LOG_LEVEL

    def test_core_logger_emits(self, caplog):
        import logging
        with caplog.at_level(logging.INFO, logger='core'):
            logging.getLogger('core.test').info('hello-from-test')
        assert 'hello-from-test' in caplog.text
