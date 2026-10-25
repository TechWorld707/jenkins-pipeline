"""Verify local URLs and ECS secret fields configure PostgreSQL safely."""
import importlib
import os
import sys
import unittest
from unittest.mock import patch


class DatabaseConfigurationTest(unittest.TestCase):
    def tearDown(self):
        module = sys.modules.pop('app.backend.main', None)
        if module is not None:
            module.engine.dispose()

    def load_app(self, settings):
        with patch.dict(os.environ, settings, clear=True):
            return importlib.import_module('app.backend.main')

    def test_ecs_password_punctuation_is_preserved(self):
        password = 'test:@/secret?#%+with spaces'
        app = self.load_app({
            'DB_HOST': 'database.example.internal',
            'DB_NAME': 'webtech',
            'DB_USER': 'test_user',
            'DB_PASSWORD': password,
        })
        self.assertEqual(app.engine.url.password, password)
        self.assertEqual(app.engine.url.username, 'test_user')
        self.assertEqual(app.engine.url.host, 'database.example.internal')
        self.assertEqual(app.engine.url.query['sslmode'], 'require')

    def test_local_compose_url_still_works(self):
        app = self.load_app({
            'DATABASE_URL': 'postgresql://local:local-test-password@database:5432/webtech',
        })
        self.assertEqual(app.engine.url.drivername, 'postgresql+psycopg')
        self.assertEqual(app.engine.url.host, 'database')

    def test_missing_credentials_fail_before_startup(self):
        with self.assertRaisesRegex(RuntimeError, 'Supply DATABASE_URL'):
            self.load_app({'DB_HOST': 'database.example.internal'})


if __name__ == '__main__':
    unittest.main()
