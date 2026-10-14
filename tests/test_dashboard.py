import json
import unittest
from unittest.mock import patch,Mock
from dashboard import server


class DashboardTests(unittest.TestCase):
    def fixture(self,sha='abc',valid=True):
        return dict(input_sha256=sha,validation=dict(exact_snapshot_reconciliation=valid,sql_aggregate_reconciliation=valid))

    def test_stale_or_unvalidated_report_rejected(self):
        for data in [self.fixture('old'),self.fixture(valid=False)]:
            with patch.object(server,'REPORT') as path,patch.object(server,'preflight',return_value=([],{'output_sha256':'abc'})):
                path.read_text.return_value=json.dumps(data)
                with self.assertRaises(ValueError):server.load_report()

    def test_valid_current_report_accepted(self):
        data=self.fixture()
        with patch.object(server,'REPORT') as path,patch.object(server,'preflight',return_value=([],{'output_sha256':'abc'})):
            path.read_text.return_value=json.dumps(data)
            self.assertEqual(server.load_report(),data)

    def test_failed_refresh_keeps_saved_report_and_sanitizes_exception(self):
        with patch.object(server,'LOCK') as lock,patch.object(server,'save') as save,patch.object(server,'create_connection',side_effect=RuntimeError('secret credential')):
            server.refresh()
            save.assert_not_called();lock.release.assert_called_once()
            self.assertFalse(server.STATE['running'])
            self.assertNotIn('secret',server.STATE['error'])
        server.STATE.update(running=False,error=None)
