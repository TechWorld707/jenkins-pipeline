"""Guardrails for the intentionally slow JIRA-002 learning release."""
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


def load():
    spec = importlib.util.spec_from_file_location(
        'query_regression', Path(__file__).parents[1] / 'app/backend/query_regression.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The helper only needs sqlalchemy.text; exercise behavior without a DB.
        with patch.dict(sys.modules, {'sqlalchemy': MagicMock(text=lambda sql: sql)}):
            cls.module = load()

    def test_disabled_does_not_touch_database(self):
        db = MagicMock()
        self.module.QueryRegression(enabled=False).run(db, MagicMock())
        db.execute.assert_not_called()

    def test_expired_does_not_touch_database(self):
        clock = MagicMock(return_value=0)
        drill = self.module.QueryRegression(enabled=True, clock=clock)
        clock.return_value = 1800
        db = MagicMock()
        drill.run(db, MagicMock())
        db.execute.assert_not_called()

    def test_overlapping_request_is_skipped(self):
        drill = self.module.QueryRegression(enabled=True)
        drill.slot.acquire()
        db = MagicMock()
        drill.run(db, MagicMock())
        db.execute.assert_not_called()

    def test_timeout_is_set_before_query_and_restored(self):
        drill = self.module.QueryRegression(enabled=True)
        db = MagicMock()
        db.execute.return_value.scalar_one.return_value = '0'
        drill.run(db, MagicMock())
        calls = db.execute.call_args_list
        self.assertEqual(calls[0].args[0], 'SHOW statement_timeout')
        self.assertIn("'8000'", calls[1].args[0])
        self.assertIn('generate_series', calls[2].args[0])
        self.assertEqual(calls[3].args[1], {'previous': '0'})

    def test_error_propagates_and_slot_is_released(self):
        drill = self.module.QueryRegression(enabled=True)
        db, record = MagicMock(), MagicMock()
        db.execute.side_effect = RuntimeError('cancelled')
        with self.assertRaises(RuntimeError):
            drill.run(db, record)
        self.assertTrue(drill.slot.acquire(blocking=False))
        self.assertEqual(record.call_args.kwargs['outcome'], 'failed')


if __name__ == '__main__':
    unittest.main()
