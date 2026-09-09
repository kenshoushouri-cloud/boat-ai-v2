"""Real PostgreSQL smoke tests, confined to a disposable local CI database.

This is not a production audit. The only accepted server is loopback:5432,
with database audit_sandbox and the explicit sandbox marker. The fixture
creates and removes its own objects; it never reads real race data or secrets.
"""
import ipaddress
import os
import secrets
import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_odds_evidence_20260908_pg as audit
import odds_evidence_privilege_guard as guard

try:
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None

ROLE = guard.ROLE_NAME
TABLES = tuple(guard.TARGET_COLUMNS)


@unittest.skipUnless(os.environ.get('AUDIT_SQL_SMOKE') == 'DISPOSABLE_LOCAL_ONLY',
                     'Disposable PostgreSQL smoke test is not enabled')
class PostgreSQLSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if psycopg is None:
            raise unittest.SkipTest('psycopg is not installed')
        # Never accept a URL, remote host, or production database as input.
        if (os.environ.get('AUDIT_SQL_SMOKE') != 'DISPOSABLE_LOCAL_ONLY'
                or os.environ.get('AUDIT_SQL_SMOKE_DATABASE') != 'audit_sandbox'
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
        cls.created_role = False
        cls.created_tables = []
        cls.role_password = secrets.token_urlsafe(24)
        cls.reader = psycopg.conninfo.make_conninfo(
            '', host='127.0.0.1', hostaddr='127.0.0.1', port=5432,
            dbname='audit_sandbox', user=ROLE, password=cls.role_password,
            sslmode='disable', gssencmode='disable', connect_timeout=3,
            options='-c search_path=pg_catalog -c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=2000 -c idle_in_transaction_session_timeout=30000')
        try:
            identity = cls.admin.execute("""SELECT current_database() AS db,
                current_user AS role, inet_server_addr()::text AS address,
                current_setting('server_version_num')::int AS version""").fetchone()
            if (identity['db'] != 'audit_sandbox' or identity['role'] != 'postgres'
                    or not ipaddress.ip_interface(identity['address']).ip.is_private
                    or not guard.MIN_VERSION <= identity['version'] < guard.MAX_VERSION):
                raise RuntimeError('disposable_database_identity_rejected')
            if cls.admin.execute('SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=%s', (ROLE,)).fetchone():
                raise RuntimeError('disposable_role_already_exists')
            for table in TABLES:
                if cls.admin.execute('SELECT to_regclass(%s) AS relation', ('public.' + table,)).fetchone()['relation'] is not None:
                    raise RuntimeError('disposable_table_already_exists')
            cls.admin.execute(sql.SQL("""CREATE ROLE {} WITH LOGIN NOINHERIT
                NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
                PASSWORD {}""").format(sql.Identifier(ROLE), sql.Literal(cls.role_password)))
            cls.created_role = True
            definitions = {
                'v2_races': 'race_id text PRIMARY KEY, race_date date, deadline_at timestamptz, private_note text',
                'v2_race_entries': 'race_id text, lane integer',
                'v2_odds_trifecta': 'race_id text, ticket text, fetched_at timestamptz, is_final boolean',
                'v2_bao_market_shadow_snapshots': 'race_id text, phase text, captured_at timestamptz, created_at timestamptz, deadline_at timestamptz, odds numeric[], source text, schema_version integer',
            }
            for table, definition in definitions.items():
                cls.admin.execute(sql.SQL('CREATE TABLE public.{} ({})').format(
                    sql.Identifier(table), sql.SQL(definition)))
                cls.created_tables.append(table)
            cls.admin.execute(sql.SQL('GRANT CONNECT ON DATABASE audit_sandbox TO {}').format(sql.Identifier(ROLE)))
            cls.admin.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE)))
            for table, columns in guard.TARGET_COLUMNS.items():
                cls.admin.execute(sql.SQL('GRANT SELECT ({}) ON TABLE public.{} TO {}').format(
                    sql.SQL(', ').join(map(sql.Identifier, columns)), sql.Identifier(table), sql.Identifier(ROLE)))
            rid = audit.TARGET_RACES[0]
            deadline = audit.reference_deadline(rid)
            cls.admin.execute('INSERT INTO public.v2_races VALUES (%s,%s,%s,%s)',
                              (rid, audit.TARGET_DATE, deadline, 'not readable'))
            with cls.admin.cursor() as cur:
                cur.executemany('INSERT INTO public.v2_race_entries VALUES (%s,%s)',
                                [(rid, lane) for lane in range(1, 7)])
                cur.executemany('INSERT INTO public.v2_odds_trifecta VALUES (%s,%s,%s,%s)',
                                [(rid, ticket, deadline, False) for ticket in audit.ALL_TICKETS])
            cls.admin.execute('''INSERT INTO public.v2_bao_market_shadow_snapshots
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)''',
                (rid, 'early', deadline - timedelta(minutes=25),
                 deadline - timedelta(minutes=24), deadline, [2.0] * 120, 'official_odds3t', 3))
        except Exception:
            cls._cleanup()
            raise

    @classmethod
    def _cleanup(cls):
        if cls.admin.closed:
            return
        for table in reversed(cls.created_tables):
            cls.admin.execute(sql.SQL('DROP TABLE public.{}').format(sql.Identifier(table)))
        if cls.created_role:
            cls.admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
            cls.admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
        cls.admin.close()

    @classmethod
    def tearDownClass(cls):
        cls._cleanup()

    def preflight(self):
        with psycopg.connect(self.reader, row_factory=dict_row, autocommit=False) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                    return guard.preflight(cur, expected_database='audit_sandbox')
            finally:
                conn.rollback()

    def test_actual_catalog_sql_and_fixed_scope(self):
        result = audit.read_database(self.reader, expected_database='audit_sandbox')
        self.assertEqual(result['privilege_preflight']['status'], 'BOUNDED_PRIVILEGE_PREFLIGHT_PASSED')
        self.assertEqual(len(result['races']), 19)
        self.assertTrue(result['races'][0]['base']['complete'])
        self.assertEqual(result['races'][0]['base']['expected'], 120)
        self.assertEqual(result['races'][0]['independent_source_verification'], 'NOT_PERFORMED')
        self.assertEqual(result['historical_roi_approval'], 'BLOCKED')
        self.assertEqual(result['root_cause'], 'UNDETERMINED')
        with psycopg.connect(self.reader, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    cur.execute('SELECT private_note FROM public.v2_races')

    def test_database_create_grant_is_rejected(self):
        self.admin.execute(sql.SQL('GRANT CREATE ON DATABASE audit_sandbox TO {}').format(sql.Identifier(ROLE)))
        try:
            with self.assertRaises(guard.PrivilegeGuardError):
                self.preflight()
        finally:
            self.admin.execute(sql.SQL('REVOKE CREATE ON DATABASE audit_sandbox FROM {}').format(sql.Identifier(ROLE)))

    def test_extra_column_and_write_grants_are_rejected(self):
        for privilege in ('SELECT (private_note)', 'INSERT'):
            with self.subTest(privilege=privilege):
                self.admin.execute(sql.SQL('GRANT {} ON public.v2_races TO {}').format(
                    sql.SQL(privilege), sql.Identifier(ROLE)))
                try:
                    with self.assertRaises(guard.PrivilegeGuardError):
                        self.preflight()
                finally:
                    self.admin.execute(sql.SQL('REVOKE {} ON public.v2_races FROM {}').format(
                        sql.SQL(privilege), sql.Identifier(ROLE)))

    def test_role_membership_is_rejected(self):
        self.admin.execute(sql.SQL('GRANT pg_read_all_data TO {}').format(sql.Identifier(ROLE)))
        try:
            with self.assertRaises(guard.PrivilegeGuardError):
                self.preflight()
        finally:
            self.admin.execute(sql.SQL('REVOKE pg_read_all_data FROM {}').format(sql.Identifier(ROLE)))


if __name__ == '__main__':
    unittest.main()
