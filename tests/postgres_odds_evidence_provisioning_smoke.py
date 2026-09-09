"""Disposable PostgreSQL test for the unexecuted production role contract.

This test is hard-gated to the loopback audit_sandbox CI service. It performs
DDL only inside that disposable database and never uses Railway credentials.
"""
import os
import secrets
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import odds_evidence_privilege_guard as guard
import odds_evidence_role_provisioning as provisioning

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None


@unittest.skipUnless(os.environ.get('AUDIT_SQL_SMOKE') == 'DISPOSABLE_LOCAL_ONLY',
                     'Disposable PostgreSQL smoke test is not enabled')
class ProvisioningPostgreSQLSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if psycopg is None:
            raise unittest.SkipTest('psycopg is not installed')
        if (os.environ.get('AUDIT_SQL_SMOKE_DATABASE') != 'audit_sandbox'
                or os.environ.get('AUDIT_SQL_SMOKE_HOST') != '127.0.0.1'):
            raise RuntimeError('disposable_database_identity_rejected')
        password = os.environ.get('AUDIT_SQL_SMOKE_ADMIN_PASSWORD')
        if not password:
            raise RuntimeError('disposable_database_credentials_missing')
        cls.admin = psycopg.connect(
            host='127.0.0.1', hostaddr='127.0.0.1', port=5432,
            dbname='audit_sandbox', user='postgres', password=password,
            sslmode='disable', gssencmode='disable', connect_timeout=3,
            autocommit=True, row_factory=dict_row,
            options='-c search_path=pg_catalog')
        cls.role_password = secrets.token_urlsafe(32)
        cls.tables = []
        if cls.admin.execute('SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=%s',
                             (guard.ROLE_NAME,)).fetchone():
            raise RuntimeError('disposable_role_already_exists')
        # PostgreSQL 14 grants CREATE on public to PUBLIC by default. The live
        # provisioner deliberately does not change PUBLIC, so the disposable
        # fixture removes that default to model the required production state.
        cls.admin.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        definitions = {
            'v2_races': 'race_id text, race_date date, deadline_at timestamptz, private_note text',
            'v2_race_entries': 'race_id text, lane integer',
            'v2_odds_trifecta': 'race_id text, ticket text, fetched_at timestamptz, is_final boolean',
        }
        for table, definition in definitions.items():
            cls.admin.execute(sql.SQL('CREATE TABLE public.{} ({})').format(
                sql.Identifier(table), sql.SQL(definition)))
            cls.tables.append(table)

    @classmethod
    def tearDownClass(cls):
        try:
            if not cls.admin.closed:
                if cls.admin.execute('SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=%s',
                                     (guard.ROLE_NAME,)).fetchone():
                    cls.admin.execute(sql.SQL('DROP OWNED BY {}').format(
                        sql.Identifier(guard.ROLE_NAME)))
                    cls.admin.execute(sql.SQL('DROP ROLE {}').format(
                        sql.Identifier(guard.ROLE_NAME)))
                for table in reversed(cls.tables):
                    cls.admin.execute(sql.SQL('DROP TABLE IF EXISTS public.{}').format(
                        sql.Identifier(table)))
        finally:
            cls.admin.close()

    def reader_conninfo(self):
        return psycopg.conninfo.make_conninfo(
            '', host='127.0.0.1', hostaddr='127.0.0.1', port=5432,
            dbname='audit_sandbox', user=guard.ROLE_NAME,
            password=self.role_password, sslmode='disable', gssencmode='disable',
            connect_timeout=3, options='-c search_path=pg_catalog')

    def test_apply_is_transactional_and_rolls_back_cleanly(self):
        with self.admin.transaction():
            with self.admin.cursor() as cur:
                result = provisioning.apply(
                    cur, database='audit_sandbox', password=self.role_password,
                    confirmation=provisioning.CONFIRMATION)
                self.assertEqual(result['status'],
                                 'AUDIT_ROLE_PROVISIONING_APPLIED_UNCOMMITTED')
                self.assertEqual(set(result['granted_tables']), set(guard.REQUIRED_TABLES))
                self.assertNotIn('v2_bao_market_shadow_snapshots', result['granted_tables'])
            # Force rollback to prove the helper does not require or perform COMMIT.
            raise psycopg.Rollback()
        self.assertIsNone(self.admin.execute(
            'SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=%s',
            (guard.ROLE_NAME,)).fetchone())

    def test_committed_disposable_contract_passes_real_preflight(self):
        with self.admin.transaction():
            with self.admin.cursor() as cur:
                provisioning.apply(cur, database='audit_sandbox',
                                   password=self.role_password,
                                   confirmation=provisioning.CONFIRMATION)
        role = self.admin.execute("""SELECT rolcanlogin, rolinherit, rolsuper,
            rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolconnlimit
            FROM pg_catalog.pg_roles WHERE rolname=%s""", (guard.ROLE_NAME,)).fetchone()
        self.assertEqual(role, dict(rolcanlogin=True, rolinherit=False, rolsuper=False,
                                   rolcreatedb=False, rolcreaterole=False,
                                   rolreplication=False, rolbypassrls=False,
                                   rolconnlimit=1))
        with psycopg.connect(self.reader_conninfo(), row_factory=dict_row,
                             autocommit=False) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                    result = guard.preflight(cur, expected_database='audit_sandbox')
                    self.assertEqual(result['status'],
                                     'BOUNDED_PRIVILEGE_PREFLIGHT_PASSED')
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        cur.execute('SELECT private_note FROM public.v2_races')
            finally:
                conn.rollback()
        self.admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(guard.ROLE_NAME)))
        self.admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(guard.ROLE_NAME)))


if __name__ == '__main__':
    unittest.main()
