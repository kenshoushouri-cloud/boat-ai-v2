"""Offline safety tests for the one-shot Railway-backed audit runner."""
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
import run_odds_evidence_20260908 as runner


class ManualAuditTests(unittest.TestCase):
    def context(self):
        return {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": runner.REPO,
                "GITHUB_REF": "refs/heads/" + runner.BRANCH,
                "GITHUB_ACTOR": "kenshoushouri-cloud", "AUDIT_DATE": audit.TARGET_DATE,
                "AUDIT_CONFIRMATION": runner.CONFIRMATION, "RAILWAY_TOKEN": "test-secret"}

    def response(self, **changes):
        data = {"projectToken": {"projectId": runner.PROJECT, "environmentId": runner.ENVIRONMENT},
                "service": {"id": runner.SERVICE, "name": "postgres-recovery"},
                "variables": {"DATABASE_PUBLIC_URL": "postgresql://reader:secret@x.proxy.rlwy.net:1234/railway"}}
        data.update(changes)
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit): return json.dumps({"data": data}).encode()
        return Response()

    def test_authorization_is_exact_and_fail_closed(self):
        env = self.context()
        runner.authorize(env)
        for key in env:
            with self.subTest(key=key):
                modified = dict(env, **{key: "" if key == "RAILWAY_TOKEN" else "wrong"})
                with self.assertRaises(runner.AuditGuardError): runner.authorize(modified)

    def test_api_is_a_fixed_read_only_query(self):
        seen = []
        def opener(request, timeout):
            seen.append((request, timeout))
            return self.response()
        self.assertIn("proxy.rlwy.net", runner.resolve_public_url("test-secret", opener))
        request, timeout = seen[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["variables"], {"p": runner.PROJECT, "e": runner.ENVIRONMENT, "s": runner.SERVICE})
        self.assertIn("query AuditConnection", payload["query"])
        self.assertNotIn("mutation ", payload["query"])
        self.assertEqual(timeout, 15)
        self.assertEqual(request.get_header("Project-access-token"), "test-secret")

    def test_api_identity_and_missing_url_fail_closed(self):
        for change in ({"projectToken": {"projectId": "wrong", "environmentId": runner.ENVIRONMENT}},
                       {"service": {"id": runner.SERVICE, "name": "postgres"}},
                       {"variables": {}}, {"variables": {"DATABASE_PUBLIC_URL": ""}}):
            with self.subTest(change=change):
                with self.assertRaises(runner.AuditGuardError):
                    runner.resolve_public_url("secret", lambda *a, **k: self.response(**change))

    def test_api_errors_do_not_expose_secrets(self):
        secret = "private-token-never-print"
        with self.assertRaises(runner.AuditGuardError) as error:
            runner.resolve_public_url(secret, lambda *a, **k: (_ for _ in ()).throw(RuntimeError(secret)))
        self.assertNotIn(secret, str(error.exception))

    def test_connection_rejects_nonpublic_or_malformed_urls(self):
        for url in ("postgresql://u:p@localhost:5432/db", "postgresql://u:p@postgres.railway.internal:5432/db",
                    "postgresql://u:p@127.0.0.1:5432/db", "https://u:p@x.proxy.rlwy.net:5432/db",
                    "postgresql://u:p@x.proxy.rlwy.net/db", "postgresql://u:p@x.proxy.rlwy.net:5432/",
                    "postgresql://u:p@evilproxy.rlwy.net:5432/db",
                    "postgresql://u:p@x.proxy.rlwy.net.evil.test:5432/db",
                    "postgresql://u:p@.proxy.rlwy.net:5432/db",
                    "postgresql://u:p@-x.proxy.rlwy.net:5432/db",
                    "postgresql://u:p@x.proxy.rlwy.net:0/db",
                    "postgresql://u:p@x.proxy.rlwy.net:65536/db",
                    "postgresql://u@x.proxy.rlwy.net:5432/db",
                    "postgresql://u:p@x.proxy.rlwy.net:bad/db",
                    "postgresql://u:p@x.proxy.rlwy.net:5432/db%2Fother",
                    "postgresql://u:p@x.proxy.rlwy.net:5432/db#fragment",
                    "postgresql://u:p@x.proxy.rlwy.net:5432/db?x=%ZZ"):
            with self.subTest(url=url):
                with self.assertRaises(runner.AuditGuardError): runner.connection_info(url)

    def test_invalid_urls_do_not_import_database_driver(self):
        with patch.dict(sys.modules, {"psycopg": None, "psycopg.conninfo": None}):
            with self.assertRaisesRegex(runner.AuditGuardError, "public_database_url_invalid"):
                runner.connection_info("postgresql://u:p@localhost:5432/db")

    def test_connection_forces_readonly_and_discards_url_options(self):
        captured = {}
        def make_conninfo(*args, **kwargs):
            captured.update(kwargs)
            return "sanitized-connection"
        fake = types.ModuleType("psycopg")
        conninfo = types.ModuleType("psycopg.conninfo")
        conninfo.make_conninfo = make_conninfo
        with patch.dict(sys.modules, {"psycopg": fake, "psycopg.conninfo": conninfo}):
            result = runner.connection_info("postgresql://reader:p%40ss@x.proxy.rlwy.net:1234/railway?sslmode=disable&options=-c%20default_transaction_read_only%3Doff")
        self.assertEqual(result, "sanitized-connection")
        self.assertEqual(captured["password"], "p@ss")
        self.assertEqual(captured["sslmode"], "require")
        self.assertIn("default_transaction_read_only=on", captured["options"])
        self.assertNotIn("default_transaction_read_only=off", str(captured))
        self.assertEqual(captured["connect_timeout"], 10)

    def test_safe_report_drops_raw_market_metadata(self):
        result = audit.analyze([], [], [], [], {"bao_snapshots_available": False})
        result["races"][0]["base"]["unexpected"] = ["private-data"]
        result["races"][0]["snapshots"] = [{"status": "UNVERIFIED", "source": "private-data", "odds": [123]}]
        report = runner.safe_report(result)
        self.assertEqual(len(report["races"]), 19)
        self.assertNotIn("private-data", json.dumps(report))
        self.assertEqual(report["historical_roi_approval"], "BLOCKED")
        self.assertEqual(report["root_cause"], "UNDETERMINED")
        self.assertEqual(report["races"][0]["base"]["unexpected_count"], 1)

    def test_main_failure_does_not_publish_exception_or_write(self):
        with patch.object(runner, "resolve_public_url", side_effect=RuntimeError("private-secret")), \
             patch.object(runner, "OUTPUT") as output, contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(runner.main(self.context()), 1)
        self.assertNotIn("private-secret", stderr.getvalue())
        output.write_text.assert_not_called()

    def test_main_rejects_unauthorized_before_network(self):
        with patch.object(runner, "resolve_public_url") as resolve:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main({}), 1)
        resolve.assert_not_called()

    def test_main_success_writes_only_sanitized_report(self):
        result = audit.analyze([], [], [], [], {"bao_snapshots_available": False})
        with patch.object(runner, "resolve_public_url", return_value="url"), \
             patch.object(runner, "connection_info", return_value="safe"), \
             patch.object(runner.audit, "read_database", return_value=result), \
             patch.object(runner, "OUTPUT") as output, contextlib.redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(runner.main(self.context()), 0)
        report = json.loads(output.write_text.call_args.args[0])
        self.assertEqual(len(report["races"]), 19)
        self.assertEqual(report["historical_roi_approval"], "BLOCKED")
        self.assertNotIn("url", stdout.getvalue())

    def test_workflow_is_manual_only_and_has_no_deploy_permissions(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/odds-evidence-audit-manual.yml").read_text()
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("pull_request_target:", text)
        self.assertNotIn("issue_comment:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("railway up", text)
        self.assertNotIn("railway redeploy", text)
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("github.ref == 'refs/heads/" + runner.BRANCH + "'", text)
        self.assertIn("retention-days: 7", text)
        self.assertNotIn("pull_request:\n", text)


if __name__ == "__main__":
    unittest.main()
