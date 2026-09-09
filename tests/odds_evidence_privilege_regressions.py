"""Offline tests: no external network, database, or real credentials."""
import contextlib
import io
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_odds_evidence_20260908_pg as audit
import odds_evidence_privilege_guard as guard
import run_odds_evidence_20260908 as runner


class CatalogCursor:
    def __init__(self, version=150000, **changes):
        self.commands = []
        self.version = version
        self.changes = changes
        self.query = ''
    def execute(self, query, params=()):
        self.query = query
        self.commands.append((query, params))
    def fetchmany(self, limit):
        if self.changes.get('unavailable'):
            raise RuntimeError('private-secret')
        if 'server_version_num' in self.query:
            row = dict(version=self.version, read_only='on', login_role=guard.ROLE_NAME,
                       active_role=guard.ROLE_NAME, database_name='railway', role_oid=123,
                       rolsuper=False, rolcreatedb=False, rolcreaterole=False,
                       rolreplication=False, rolbypassrls=False, rolinherit=False,
                       rolcanlogin=True)
        elif 'relation_exists' in self.query:
            row = dict(relation_exists=True, columns_readable=True)
        else:
            import re
            names = re.findall(r'AS ([a-z_]+)', self.query)
            row = {name: False for name in names}
        row.update({k: v for k, v in self.changes.items() if k in row})
        return [row]


class PrivilegeTests(unittest.TestCase):
    def test_known_versions(self):
        for version in (140000, 150000, 160000, 170000, 180000):
            with self.subTest(version=version):
                cur = CatalogCursor(version)
                self.assertEqual(guard.preflight(cur, expected_database='railway')['status'],
                                 'BOUNDED_PRIVILEGE_PREFLIGHT_PASSED')
                sql = '\n'.join(q for q, _ in cur.commands)
                self.assertEqual('pg_parameter_acl' in sql, version >= 150000)
                self.assertEqual(any('MAINTAIN' in str(params) for _, params in cur.commands), version >= 170000)
                self.assertTrue(all(q.lstrip().startswith('SELECT') for q, _ in cur.commands))
                self.assertTrue(all(len(p) <= 7 for _, p in cur.commands))
    def test_builtin_defaults_do_not_hide_application_writes(self):
        cur = CatalogCursor()
        guard.preflight(cur, expected_database='railway')
        query = next(q for q, _ in cur.commands if 'database_write' in q)
        self.assertIn("a.privilege_type = 'TEMP'", query)
        self.assertIn("has_database_privilege(d.oid, 'CREATE')", query)
        self.assertIn("c.relname = 'pg_settings'", query)
        self.assertIn("has_table_privilege(c.oid, 'UPDATE')", query)
        self.assertIn("has_column_privilege(c.oid, a.attnum, 'UPDATE')", query)
        self.assertIn('lanispl AND NOT lanpltrusted', query)
        params = next(p for q, p in cur.commands if 'database_write' in q)
        self.assertEqual(params[4], 'INSERT, DELETE, TRUNCATE, REFERENCES, TRIGGER')
        self.assertIn('UPDATE WITH GRANT OPTION', params[5])

    def test_sequence_privilege_checks_guard_relation_kind(self):
        cur = CatalogCursor()
        guard.preflight(cur, expected_database='railway')
        query = next(q for q, _ in cur.commands if 'sequence_access' in q)
        self.assertEqual(query.count("WHERE CASE WHEN relkind = 'S'"), 2)
        self.assertEqual(query.count('ELSE false END'), 2)

    def test_largeobject_acl_is_compatible_with_postgresql_14_through_18(self):
        cur = CatalogCursor()
        guard.preflight(cur, expected_database='railway')
        sql = '\n'.join(q for q, _ in cur.commands)
        self.assertIn("pg_catalog.acldefault('L', lo.lomowner)", sql)
        self.assertIn('a.grantee IN (0, %s)', sql)
        self.assertIn("a.privilege_type IN ('SELECT', 'UPDATE')", sql)
        self.assertNotIn('has_largeobject_privilege', sql)
        self.assertEqual(next(params for query, params in cur.commands
                              if 'largeobject_access' in query)[-1], 123)

    def test_grant_options_and_parameter_rights_are_explicit(self):
        cur = CatalogCursor(version=170000)
        guard.preflight(cur, expected_database='railway')
        sql = '\n'.join(q for q, _ in cur.commands)
        self.assertIn('CREATE WITH GRANT OPTION, CONNECT WITH GRANT OPTION, TEMP WITH GRANT OPTION', sql)
        self.assertIn("'SET WITH GRANT OPTION, ALTER SYSTEM WITH GRANT OPTION'", sql)
        self.assertIn('MAINTAIN WITH GRANT OPTION', str(cur.commands))
        self.assertIn('INSERT WITH GRANT OPTION', sql)
        self.assertIn('UPDATE WITH GRANT OPTION', sql)
        self.assertIn('USAGE WITH GRANT OPTION, SELECT WITH GRANT OPTION', sql)

    def test_identity_and_unsupported_versions(self):
        for change in ({'version':130000}, {'version':190000}, {'version':True},
                       {'read_only':'off'}, {'login_role':'postgres'}, {'active_role':'postgres'},
                       {'database_name':'other'}, {'role_oid':None}, {'rolsuper':True},
                       {'rolcreatedb':True}, {'rolcreaterole':True}, {'rolreplication':True},
                       {'rolbypassrls':True}, {'rolinherit':True}, {'rolcanlogin':False}):
            with self.subTest(change=change):
                with self.assertRaises(guard.PrivilegeGuardError):
                    guard.preflight(CatalogCursor(**change), expected_database='railway')
    def test_rejects_every_catalog_privilege(self):
        cur = CatalogCursor()
        cur.execute('SELECT AS dummy')
        names = ['memberships','owns_objects','default_acl_owner','database_write',
                 'database_grant','schema_write','schema_grant','tablespace_write',
                 'tablespace_grant','table_write','table_grant','column_write','column_grant',
                 'sequence_access','sequence_grant','extra_routine_execute','routine_grant',
                 'untrusted_language','language_grant','foreign_wrapper','foreign_server',
                 'largeobject_access','type_grant','parameter_grant','privileged_parameter',
                 'unexpected_target_kind','extra_table_read','extra_column_read',
                 'missing_schema_usage','target_rls','broad_target_read','extra_target_column_read']
        for name in names:
            with self.subTest(name=name):
                with self.assertRaises(guard.PrivilegeGuardError):
                    guard.preflight(CatalogCursor(**{name: True}), expected_database='railway')
    def test_required_columns_and_optional_table(self):
        for change in ({'relation_exists':False}, {'columns_readable':False},
                       {'columns_readable':None}):
            with self.subTest(change=change):
                with self.assertRaises(guard.PrivilegeGuardError):
                    guard.preflight(CatalogCursor(**change), expected_database='railway')
        class OptionalMissing(CatalogCursor):
            def fetchmany(self, limit):
                rows = super().fetchmany(limit)
                if 'relation_exists' in self.query and self.commands[-1][1][0] == 'v2_bao_market_shadow_snapshots':
                    rows[0]['relation_exists'] = False
                return rows
        guard.preflight(OptionalMissing(), expected_database='railway')
    def test_fail_closed_and_sanitized(self):
        for db in ('', None, 'x'*64):
            with self.assertRaises(guard.PrivilegeGuardError):
                guard.preflight(CatalogCursor(), expected_database=db)
        with self.assertRaises(guard.PrivilegeGuardError) as err:
            guard.preflight(CatalogCursor(unavailable=True), expected_database='railway')
        self.assertNotIn('private-secret', str(err.exception))
        class Empty(CatalogCursor):
            def fetchmany(self, limit): return []
        with self.assertRaises(guard.PrivilegeGuardError):
            guard.preflight(Empty(), expected_database='railway')
    def test_required_sql_is_bounded_and_qualified(self):
        cur = CatalogCursor()
        guard.preflight(cur, expected_database='railway')
        sql = '\n'.join(q for q, _ in cur.commands)
        self.assertIn('pg_auth_members', sql)
        self.assertIn('pg_shdepend', sql)
        self.assertIn('pg_catalog.has_column_privilege', sql)
        self.assertIn('extra_target_column_read', sql)
        self.assertIn('broad_target_read', sql)
        self.assertIn('target_rls', sql)
        self.assertIn('pg_catalog.pg_parameter_acl', sql)
        self.assertIn('pg_catalog.pg_default_acl', sql)
        self.assertNotIn('FROM v2_races', sql)
        self.assertNotIn('DATABASE_URL', sql)


class RunnerTests(unittest.TestCase):
    URL = 'postgresql://boat_odds_audit_ro:p%40ss@x.proxy.rlwy.net:1234/railway'
    def context(self):
        return dict(GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REPOSITORY=runner.REPO,
            GITHUB_REF='refs/heads/'+runner.BRANCH, GITHUB_ACTOR='kenshoushouri-cloud',
            AUDIT_DATE=audit.TARGET_DATE, AUDIT_CONFIRMATION=runner.CONFIRMATION,
            AUDIT_DATABASE_URL=self.URL, AUDIT_DB_HOST='x.proxy.rlwy.net',
            AUDIT_DB_PORT='1234', AUDIT_DB_NAME='railway')
    def test_missing_credentials_and_identity(self):
        env = self.context()
        runner.authorize(env)
        for key in env:
            with self.subTest(key=key):
                bad = dict(env); bad.pop(key)
                with self.assertRaises(runner.AuditGuardError): runner.authorize(bad)
        with self.assertRaises(runner.AuditGuardError):
            runner.authorize(dict(DATABASE_URL=self.URL, RAILWAY_TOKEN='test-secret'))
        self.assertFalse(hasattr(runner, 'resolve_public_url'))
    def test_connection_validation_before_driver_import(self):
        kwargs = dict(expected_host='x.proxy.rlwy.net', expected_port='1234', expected_database='railway')
        bad = [self.URL.replace('boat_odds_audit_ro', 'postgres'),
               self.URL.replace('x.proxy.rlwy.net', 'localhost'),
               self.URL.replace('1234', '1235'), self.URL.replace('/railway', '/other'),
               self.URL+'#fragment', self.URL.replace('1234','bad')]
        with patch.dict(sys.modules, {'psycopg': None, 'psycopg.conninfo': None}):
            for url in bad:
                with self.subTest(url=url):
                    with self.assertRaises(runner.AuditGuardError): runner.connection_info(url, **kwargs)
            with self.assertRaises(runner.AuditGuardError):
                runner.connection_info(self.URL, expected_host='other.proxy.rlwy.net',
                    expected_port='1234', expected_database='railway')
    def test_connection_security_options(self):
        seen = {}
        fake = types.ModuleType('psycopg')
        conninfo = types.ModuleType('psycopg.conninfo')
        def make_conninfo(*args, **kwargs):
            seen.update(kwargs); return 'safe-conninfo'
        conninfo.make_conninfo = make_conninfo
        with patch.dict(sys.modules, {'psycopg':fake, 'psycopg.conninfo':conninfo}):
            result = runner.connection_info(self.URL+'?sslmode=disable&options=unsafe',
                expected_host='x.proxy.rlwy.net', expected_port='1234', expected_database='railway')
        self.assertEqual(result, 'safe-conninfo')
        self.assertEqual(seen['user'], guard.ROLE_NAME)
        self.assertEqual(seen['password'], 'p@ss')
        self.assertEqual(seen['sslmode'], 'verify-full')
        self.assertEqual(seen['gssencmode'], 'disable')
        self.assertIn('default_transaction_read_only=on', seen['options'])
        self.assertNotIn('unsafe', str(seen))
    def test_unauthorized_no_connection_or_output(self):
        with patch.object(runner, 'connection_info') as connect, patch.object(runner, 'OUTPUT') as out:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main({}), 1)
        connect.assert_not_called(); out.write_text.assert_not_called()
    def test_failure_is_sanitized(self):
        with patch.object(runner, 'connection_info', side_effect=RuntimeError('private-secret')):
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(runner.main(self.context()), 1)
        self.assertNotIn('private-secret', err.getvalue())
    def test_success_is_sanitized_and_fixed(self):
        result = audit.analyze([], [], [], [], {'bao_snapshots_available':False})
        result['privilege_preflight'] = {'status':'BOUNDED_PRIVILEGE_PREFLIGHT_PASSED','server_version':150000}
        with patch.object(runner, 'connection_info', return_value='safe'), \
             patch.object(runner.audit, 'read_database', return_value=result) as read, \
             patch.object(runner, 'OUTPUT') as out, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(self.context()), 0)
        read.assert_called_once_with('safe', expected_database='railway')
        report = json.loads(out.write_text.call_args.args[0])
        self.assertEqual(len(report['races']), 19)
        self.assertEqual(report['historical_roi_approval'], 'BLOCKED')
        self.assertEqual(report['root_cause'], 'UNDETERMINED')
        self.assertEqual(report['privilege_preflight'], 'BOUNDED_PRIVILEGE_PREFLIGHT_PASSED')
    def test_direct_cli_uses_authorized_runner(self):
        with patch.object(sys, 'argv', ['audit']), patch.object(runner, 'main', return_value=17) as main:
            with self.assertRaises(SystemExit) as err: audit.main()
        self.assertEqual(err.exception.code, 17); main.assert_called_once_with()
    def test_analysis_scope_and_provenance(self):
        self.assertEqual(len(audit.TARGET_RACES),19)
        self.assertEqual(len(audit.ALL_TICKETS),120)
        result = audit.analyze([], [], [], [], {})
        self.assertEqual(result['historical_roi_approval'],'BLOCKED')
        self.assertEqual(result['races'][0]['base']['expected'],120)
        self.assertEqual(result['races'][0]['independent_source_verification'],'NOT_PERFORMED')
    def test_workflow_contract(self):
        root = Path(__file__).resolve().parents[1]
        manual = (root/'.github/workflows/odds-evidence-audit-manual.yml').read_text()
        offline = (root/'.github/workflows/odds-evidence-audit-tests.yml').read_text()
        self.assertIn('workflow_dispatch:',manual)
        self.assertIn('secrets.AUDIT_DATABASE_URL',manual)
        self.assertNotIn('secrets.RAILWAY_TOKEN',manual)
        self.assertNotIn('secrets.DATABASE_URL',manual)
        self.assertIn('contents: read',manual)
        self.assertIn('persist-credentials: false',manual)
        self.assertIn('retention-days: 7',manual)
        for forbidden in ('pull_request_target:', 'issue_comment:', 'schedule:', 'railway up', 'railway redeploy'):
            self.assertNotIn(forbidden,manual)
        self.assertIn('odds_evidence_privilege_guard.py',offline)
        self.assertIn('test_odds_evidence_privilege.py',offline)
        self.assertIn("AUDIT_DATABASE_URL: ''",offline)
        self.assertIn('DATABASE_URL: \x27\x27',offline)


class DatabaseTests(unittest.TestCase):
    def fake_database(self, *, fail_gate=False, excess=False, snapshots=True):
        class Cursor:
            def __init__(self): self.commands=[]; self.query=''; self.params=(); self.limits=[]
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def execute(self,query,params=()):
                self.query=query; self.params=params; self.commands.append((query,params))
            def fetchmany(self,limit):
                self.limits.append(limit)
                if excess: return [dict()]*(audit.MAX_ROWS+1)
                if 'information_schema.columns' in self.query:
                    required={'v2_races':('race_id','race_date','deadline_at'),
                      'v2_race_entries':('race_id','lane'),
                      'v2_odds_trifecta':('race_id','ticket','fetched_at','is_final')}
                    if snapshots: required['v2_bao_market_shadow_snapshots']=guard.TARGET_COLUMNS['v2_bao_market_shadow_snapshots']
                    return [dict(table_name=t,column_name=c) for t,cs in required.items() for c in cs]
                if 'FROM public.v2_races' in self.query: return []
                if 'FROM public.v2_race_entries' in self.query: return []
                if 'FROM public.v2_odds_trifecta' in self.query: return []
                return []
        class Connection:
            def __init__(self): self.cur=Cursor(); self.rollbacks=0
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def cursor(self): return self.cur
            def rollback(self): self.rollbacks+=1
        conn=Connection()
        fake=types.ModuleType('psycopg'); fake.connect=lambda *a,**k:conn
        rows=types.ModuleType('psycopg.rows'); rows.dict_row=object()
        return conn, {'psycopg':fake,'psycopg.rows':rows}
    def test_gate_precedes_all_data(self):
        conn,modules=self.fake_database()
        def fail(*args,**kwargs): raise guard.PrivilegeGuardError('privilege_preflight_rejected')
        with patch.dict(sys.modules,modules), patch.object(guard,'preflight',side_effect=fail):
            with self.assertRaises(guard.PrivilegeGuardError):
                audit.read_database('fake',expected_database='railway')
        self.assertEqual(conn.rollbacks,1)
        self.assertEqual(len(conn.cur.commands),4)
        self.assertTrue(all(q.startswith('SET ') for q,p in conn.cur.commands))
    def test_success_has_fixed_scope_and_rollback(self):
        conn,modules=self.fake_database()
        with patch.dict(sys.modules,modules), patch.object(guard,'preflight',return_value={'status':'BOUNDED_PRIVILEGE_PREFLIGHT_PASSED','server_version':150000}):
            result=audit.read_database('fake',expected_database='railway')
        self.assertEqual(conn.rollbacks,1)
        self.assertEqual(len(result['races']),19)
        self.assertEqual(result['privilege_preflight']['server_version'],150000)
        data=[(q,p) for q,p in conn.cur.commands if 'race_id=ANY(%s)' in q]
        self.assertEqual(len(data),4)
        self.assertTrue(all(p[-1]==list(audit.TARGET_RACES) for q,p in data))
        self.assertTrue(all(q.lstrip().startswith(('SET ','SELECT ')) for q,p in conn.cur.commands))
        self.assertTrue(all(n<=audit.MAX_ROWS+1 for n in conn.cur.limits))
    def test_row_limit_rolls_back(self):
        conn,modules=self.fake_database(excess=True)
        with patch.dict(sys.modules,modules), patch.object(guard,'preflight',return_value={'status':'BOUNDED_PRIVILEGE_PREFLIGHT_PASSED','server_version':150000}):
            with self.assertRaisesRegex(RuntimeError,'row limit exceeded'):
                audit.read_database('fake',expected_database='railway')
        self.assertEqual(conn.rollbacks,1)
    def test_missing_identity_before_driver_import(self):
        with patch.dict(sys.modules,{'psycopg':None,'psycopg.rows':None}):
            with self.assertRaises(guard.PrivilegeGuardError):
                audit.read_database('fake',expected_database='')

if __name__=='__main__': unittest.main()
