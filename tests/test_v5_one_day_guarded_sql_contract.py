"""Review exact GitHub-pinned first-day SQL without touching PostgreSQL."""
from pathlib import Path
import tempfile
import unittest

from v5.offline_one_day_stream_cap import StreamStopped, reviewed_select_statements

SOURCE = Path(__file__).resolve().parents[1] / "ops" / "v5_one_day_archived_size_guarded_readonly.sql"


class GuardedSqlContract(unittest.TestCase):
    def test_exact_sql_verified_three_separate_statements(self):
        blocks = reviewed_select_statements(SOURCE)
        self.assertEqual(set(blocks), {"Q1", "Q2", "Q3"})
        for query in blocks.values():
            self.assertEqual(query.count("(end_day - start_day) = 1"), 1)
            self.assertEqual(query.count("%(start_date)s"), 1)
            self.assertEqual(query.count("%(end_exclusive)s"), 1)
            self.assertNotIn("LIMIT ", query)
            self.assertNotIn("DISTINCT ", query)

    def test_oversize_becomes_null_not_truncated(self):
        blocks = reviewed_select_statements(SOURCE)
        q1, q2, q3 = (blocks[x] for x in ("Q1", "Q2", "Q3"))
        for query in (q1, q2, q3):
            self.assertIn("octet_length(r.race_id) <= 32", query)
            self.assertIn("ELSE NULL::text END AS race_id", query)
        self.assertIn("pg_column_size(e.recent_form) <= 12000", q2)
        self.assertIn("octet_length(e.recent_form::text) <= 12000", q2)
        self.assertIn("ELSE NULL::jsonb\n       END AS parsed_history", q2)
        self.assertIn("pg_column_size(x.raw) <= 4096", q2)
        self.assertIn("octet_length(x.raw::text) <= 4096", q2)
        self.assertIn("THEN x.raw ELSE NULL::jsonb", q2)
        self.assertIn("octet_length(rs.trifecta_ticket) <= 16", q3)

    def test_q2_does_not_read_result_or_payout(self):
        blocks = reviewed_select_statements(SOURCE)
        for forbidden in ("trifecta_ticket", "payout_per_100_yen", "v2_results"):
            self.assertNotIn(forbidden, blocks["Q2"])
        self.assertIn("LEFT JOIN public.v2_results", blocks["Q3"])
        self.assertIn("NULL::integer[] AS refund_boats", blocks["Q3"])
        self.assertIn("FALSE AS buy_eligible", blocks["Q3"])

    def test_live_candidate_v4_textual_class_only(self):
        blocks = reviewed_select_statements(SOURCE)
        q2 = blocks["Q2"]
        self.assertIn("e.racer_class_text IN ('A1','A2','B1','B2')", q2)
        self.assertIn("octet_length(e.racer_class_text) <= 8", q2)
        self.assertIn("THEN e.racer_class_text ELSE NULL::text END AS racer_class", q2)
        self.assertNotIn("e.racer_class::text", q2)
        self.assertNotIn("e.racer_class AS racer_class", q2)

    def test_seven_day_sql_and_catalog_reference_same_grade_column(self):
        root = SOURCE.parents[1]
        period = (root / "ops/v5_seven_day_archived_research_source_readonly.sql").read_text()
        catalog = (root / "ops/v5_archive_catalog_railway_data_query_readonly_20261011.sql").read_text()
        self.assertIn("e.racer_class_text IN ('A1','A2','B1','B2')", period)
        self.assertIn("THEN e.racer_class_text ELSE NULL::text END AS racer_class", period)
        self.assertIn("('v2_race_entries','racer_class_text',ARRAY['text','varchar']", catalog)
        self.assertNotIn("('v2_race_entries','racer_class',ARRAY['text','varchar']", catalog)

    def test_tampered_source_cannot_be_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "read.sql"
            p.write_bytes(SOURCE.read_bytes().replace(b"<= 12000", b"<= 12001"))
            with self.assertRaisesRegex(StreamStopped, "UNREVIEWED_SOURCE_SQL"):
                reviewed_select_statements(p)


if __name__ == "__main__":
    unittest.main()
