"""Offline contract tests for the unexecuted audit-role provisioning helper."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import odds_evidence_privilege_guard as guard
import odds_evidence_role_provisioning as provisioning


class ProvisioningContractTests(unittest.TestCase):
    def test_request_validation_is_exact_and_driver_free(self):
        good = dict(database='railway', password='x' * 32,
                    confirmation=provisioning.CONFIRMATION)
        with patch.dict(sys.modules, {'psycopg': None}):
            provisioning.validate_request(**good)
        bad = [
            dict(good, database=''),
            dict(good, database='railway/other'),
            dict(good, database='x' * 64),
            dict(good, password='short'),
            dict(good, password='x' * 23),
            dict(good, password='x' * 257),
            dict(good, password='x' * 24 + '\n'),
            dict(good, confirmation='YES'),
        ]
        for case in bad:
            with self.subTest(case={k: ('<password>' if k == 'password' else v)
                                    for k, v in case.items()}):
                with self.assertRaises(provisioning.ProvisioningError):
                    provisioning.validate_request(**case)

    def test_contract_matches_privilege_guard_scope(self):
        self.assertEqual(provisioning.ROLE_NAME, guard.ROLE_NAME)
        self.assertEqual(set(guard.REQUIRED_TABLES), {
            'v2_races', 'v2_race_entries', 'v2_odds_trifecta'})
        self.assertIn('v2_bao_market_shadow_snapshots', guard.TARGET_COLUMNS)
        self.assertEqual(provisioning.SETTINGS['default_transaction_read_only'], 'on')
        self.assertEqual(provisioning.SETTINGS['search_path'], 'pg_catalog')
        self.assertEqual(provisioning.SETTINGS['statement_timeout'], '15s')
        self.assertEqual(provisioning.SETTINGS['lock_timeout'], '2s')
        self.assertEqual(provisioning.SETTINGS['idle_in_transaction_session_timeout'], '30s')

    def test_apply_fails_before_database_driver_on_bad_request(self):
        class NeverCursor:
            def execute(self, *args, **kwargs):
                raise AssertionError('database_touched')
        with patch.dict(sys.modules, {'psycopg': None}):
            with self.assertRaises(provisioning.ProvisioningError):
                provisioning.apply(NeverCursor(), database='railway', password='short',
                                   confirmation=provisioning.CONFIRMATION)

    def test_module_has_no_connection_or_commit_surface(self):
        source = Path(provisioning.__file__).read_text(encoding='utf-8')
        self.assertNotIn('psycopg.connect', source)
        self.assertNotIn('.commit(', source)
        self.assertNotIn('DATABASE_URL', source)
        self.assertNotIn('RAILWAY_TOKEN', source)


if __name__ == '__main__':
    unittest.main()
