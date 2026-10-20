# -*- coding: utf-8 -*-
"""Local-only tests for strict V5 as-of research auditing."""
import unittest
from datetime import date
from unittest.mock import patch

from research.v5_recent_form_asof_audit_pg import (
    COVERAGE_SQL, checked_date, local_connection_url, summary_text,
)


class V5RecentFormAsOfAuditTests(unittest.TestCase):
    def test_date_is_conservative(self):
        self.assertEqual(checked_date("2026-10-20"), date(2026, 10, 20))
        with self.assertRaises(ValueError):
            checked_date("2025-06-30")
        with self.assertRaises(ValueError):
            checked_date("2035-01-01")

    def test_remote_and_other_databases_are_forbidden(self):
        self.assertEqual(local_connection_url("postgresql:///railway"), "postgresql:///railway")
        with self.assertRaisesRegex(ValueError, "local railway"):
            local_connection_url("postgresql:///postgres")
        with self.assertRaisesRegex(ValueError, "local PostgreSQL"):
            local_connection_url("postgresql://localhost/railway")

    def test_query_uses_strict_source_and_time_cutoff(self):
        self.assertIn("h.source = 'official_k_file'", COVERAGE_SQL)
        self.assertIn("h.fetched_at < %s::timestamptz", COVERAGE_SQL)
        self.assertIn("r.race_date < %s::date", COVERAGE_SQL)
        self.assertIn("h.finish_position BETWEEN 1 AND 6", COVERAGE_SQL)
        self.assertIn("history_rank <= 5", COVERAGE_SQL)
        self.assertNotIn("UPDATE public", COVERAGE_SQL.upper())

    def test_output_does_not_claim_forward_eligibility(self):
        summary = {k: 0 for k in (
            "target_entries", "target_racers", "empty_entries",
            "entries_with_asof5", "entries_under_asof5",
            "racers_with_asof5", "missing_entries_reconstructable",
        )}
        out = summary_text(summary, date(2026, 10, 20))
        self.assertIn("V5_RECENT_FORM_DB_WRITE=0", out)
        self.assertIn("V5_RECENT_FORM_FORWARD_ELIGIBLE=0", out)


if __name__ == "__main__":
    unittest.main()
