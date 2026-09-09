"""Offline regression tests for the dedicated-credential manual audit runner."""
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


class ManualAuditTests(unittest.TestCase):
    URL = 'postgresql://boat_odds_audit_ro:p%40ss@x.proxy.rlwy.net:1234/railway'
    def context(self):
        return {'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REPOSITORY':runner.REPO,
                'GITHUB_REF':'refs/heads/'+runner.BRANCH,'GITHUB_ACTOR':'kenshoushouri-cloud',
                'AUDIT_DATE':audit.TARGET_DATE,'AUDIT_CONFIRMATION':runner.CONFIRMATION,
                'AUDIT_DATABASE_URL':self.URL,'AUDIT_DB_HOST':'x.proxy.rlwy.net',
                'AUDIT_DB_PORT':'1234','AUDIT_DB_NAME':'railway'}
    def connection(self, url=None, **changes):
        args=dict(expected_host='x.proxy.rlwy.net',expected_port='1234',expected_database='railway')
        args.update(changes)
        return runner.connection_info(self.URL if url is None else url, **args)
    def result(self):
        result=audit.analyze([],[],[],[],{'bao_snapshots_available':False})
        result['privilege_preflight']={'status':'BOUNDED_PRIVILEGE_PREFLIGHT_PASSED','server_version':150000}
        return result

    def test_authorization_is_exact_and_fail_closed(self):
        env=self.context(); runner.authorize(env)
        for key in env:
            with self.subTest(key=key):
                bad=dict(env); bad[key]=''
                with self.assertRaises(runner.AuditGuardError): runner.authorize(bad)
        with self.assertRaises(runner.AuditGuardError):
            runner.authorize({'DATABASE_URL':self.URL,'RAILWAY_TOKEN':'test-secret'})

    def test_no_railway_api_or_production_credential_fallback(self):
        self.assertFalse(hasattr(runner,'resolve_public_url'))
        self.assertFalse(hasattr(runner,'PROJECT'))
        self.assertFalse(hasattr(runner,'SERVICE'))
        self.assertFalse(hasattr(runner,'ENVIRONMENT'))
        with patch.object(runner,'connection_info') as connect:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main({'DATABASE_URL':self.URL,'RAILWAY_TOKEN':'secret'}),1)
        connect.assert_not_called()

    def test_connection_rejects_nonpublic_or_malformed_urls(self):
        bad=(
            'postgresql://u:p@localhost:5432/db',
            'postgresql://u:p@postgres.railway.internal:5432/db',
            'postgresql://u:p@127.0.0.1:5432/db',
            'https://u:p@x.proxy.rlwy.net:5432/db',
            'postgresql://u:p@x.proxy.rlwy.net/db',
            'postgresql://u:p@x.proxy.rlwy.net:5432/',
            'postgresql://u:p@evilproxy.rlwy.net:5432/db',
            'postgresql://u:p@x.proxy.rlwy.net.evil.test:5432/db',
            'postgresql://u:p@.proxy.rlwy.net:5432/db',
            'postgresql://u:p@-x.proxy.rlwy.net:5432/db',
            'postgresql://u:p@x.proxy.rlwy.net:0/db',
            'postgresql://u:p@x.proxy.rlwy.net:65536/db',
            'postgresql://u@x.proxy.rlwy.net:5432/db',
            'postgresql://u:p@x.proxy.rlwy.net:bad/db',
            'postgresql://u:p@x.proxy.rlwy.net:5432/db%2Fother',
            'postgresql://u:p@x.proxy.rlwy.net:5432/db#fragment',
            'postgresql://u:p@x.proxy.rlwy.net:5432/db?x=%ZZ',
            self.URL.replace('boat_odds_audit_ro','postgres'),
            self.URL.replace('/railway','/other'),
        )
        with patch.dict(sys.modules,{'psycopg':None,'psycopg.conninfo':None}):
            for url in bad:
                with self.subTest(url=url):
                    with self.assertRaises(runner.AuditGuardError): self.connection(url)

    def test_invalid_urls_do_not_import_database_driver(self):
        with patch.dict(sys.modules,{'psycopg':None,'psycopg.conninfo':None}):
            with self.assertRaisesRegex(runner.AuditGuardError,'dedicated_database_url_invalid'):
                self.connection(self.URL,expected_host='other.proxy.rlwy.net')

    def test_connection_forces_readonly_and_discards_url_options(self):
        captured={}
        fake=types.ModuleType('psycopg'); conninfo=types.ModuleType('psycopg.conninfo')
        def make_conninfo(*args,**kwargs): captured.update(kwargs); return 'sanitized-connection'
        conninfo.make_conninfo=make_conninfo
        with patch.dict(sys.modules,{'psycopg':fake,'psycopg.conninfo':conninfo}):
            result=self.connection(self.URL+'?sslmode=disable&options=-c%20default_transaction_read_only%3Doff')
        self.assertEqual(result,'sanitized-connection')
        self.assertEqual(captured['user'],guard.ROLE_NAME)
        self.assertEqual(captured['password'],'p@ss')
        self.assertEqual(captured['sslmode'],'verify-full')
        self.assertEqual(captured['gssencmode'],'disable')
        self.assertIn('default_transaction_read_only=on',captured['options'])
        self.assertNotIn('default_transaction_read_only=off',str(captured))
        self.assertEqual(captured['connect_timeout'],10)

    def test_safe_report_drops_raw_market_metadata(self):
        result=self.result()
        result['races'][0]['base']['unexpected']=['private-data']
        result['races'][0]['snapshots']=[{'status':'UNVERIFIED','source':'private-data','odds':[123]}]
        report=runner.safe_report(result)
        self.assertEqual(len(report['races']),19)
        self.assertNotIn('private-data',json.dumps(report))
        self.assertEqual(report['historical_roi_approval'],'BLOCKED')
        self.assertEqual(report['root_cause'],'UNDETERMINED')
        self.assertEqual(report['races'][0]['base']['unexpected_count'],1)
        self.assertEqual(report['preflight_server_version'],150000)

    def test_report_requires_verified_preflight(self):
        result=self.result()
        for value in (None,{}, {'status':'BOUNDED_PRIVILEGE_PREFLIGHT_PASSED','server_version':True},
                      {'status':'BOUNDED_PRIVILEGE_PREFLIGHT_PASSED','server_version':190000},
                      {'status':'UNVERIFIED','server_version':150000}):
            with self.subTest(value=value):
                result['privilege_preflight']=value
                with self.assertRaises(runner.AuditGuardError): runner.safe_report(result)

    def test_main_failure_does_not_publish_exception_or_write(self):
        with patch.object(runner,'connection_info',side_effect=RuntimeError('private-secret')), \
             patch.object(runner,'OUTPUT') as output, contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(runner.main(self.context()),1)
        self.assertNotIn('private-secret',stderr.getvalue())
        output.write_text.assert_not_called()

    def test_main_rejects_unauthorized_before_network(self):
        with patch.object(runner,'connection_info') as connect:
            with contextlib.redirect_stderr(io.StringIO()): self.assertEqual(runner.main({}),1)
        connect.assert_not_called()

    def test_main_success_writes_only_sanitized_report(self):
        with patch.object(runner,'connection_info',return_value='safe'), \
             patch.object(runner.audit,'read_database',return_value=self.result()) as read, \
             patch.object(runner,'OUTPUT') as output, contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(runner.main(self.context()),0)
        read.assert_called_once_with('safe',expected_database='railway')
        report=json.loads(output.write_text.call_args.args[0])
        self.assertEqual(len(report['races']),19)
        self.assertEqual(report['historical_roi_approval'],'BLOCKED')
        self.assertNotIn(self.URL,stdout.getvalue())

    def test_workflow_is_manual_only_and_has_no_deploy_permissions(self):
        text=(Path(__file__).resolve().parents[1]/'.github/workflows/odds-evidence-audit-manual.yml').read_text()
        self.assertIn('workflow_dispatch:',text)
        for forbidden in ('pull_request_target:','issue_comment:','schedule:','railway up',
                          'railway redeploy','secrets.RAILWAY_TOKEN','secrets.DATABASE_URL'):
            self.assertNotIn(forbidden,text)
        self.assertIn('contents: read',text)
        self.assertIn('persist-credentials: false',text)
        self.assertIn("github.ref == 'refs/heads/"+runner.BRANCH+"'",text)
        self.assertIn('retention-days: 7',text)
        self.assertNotIn('pull_request:\n',text)

if __name__=='__main__': unittest.main()
