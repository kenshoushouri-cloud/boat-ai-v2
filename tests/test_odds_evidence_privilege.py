"""Regression suite with the canonical PostgreSQL ACL assertion."""
import odds_evidence_privilege_regressions as _regressions

CatalogCursor = _regressions.CatalogCursor
RunnerTests = _regressions.RunnerTests
DatabaseTests = _regressions.DatabaseTests

class PrivilegeTests(_regressions.PrivilegeTests):
    def test_builtin_defaults_do_not_hide_application_writes(self):
        cur = CatalogCursor()
        _regressions.guard.preflight(cur, expected_database='railway')
        query = next(q for q, _ in cur.commands if 'database_write' in q)
        self.assertIn("a.privilege_type = 'TEMPORARY'", query)
        self.assertIn("has_database_privilege(d.oid, 'CREATE')", query)
        self.assertIn("c.relname = 'pg_settings'", query)
        self.assertIn("has_table_privilege(c.oid, 'UPDATE')", query)
        self.assertIn("has_column_privilege(c.oid, a.attnum, 'UPDATE')", query)
        self.assertIn('lanispl AND NOT lanpltrusted', query)
        params = next(p for q, p in cur.commands if 'database_write' in q)
        self.assertEqual(params[4], 'INSERT, DELETE, TRUNCATE, REFERENCES, TRIGGER')
        self.assertIn('UPDATE WITH GRANT OPTION', params[5])
