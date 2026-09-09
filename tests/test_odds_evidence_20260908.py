"""Offline tests for the fixed-date, research-only odds evidence audit."""
import contextlib
import io
import math
import sys
import types
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_odds_evidence_20260908_pg as audit


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.rid = audit.TARGET_RACES[0]
        self.deadline = audit.reference_deadline(self.rid)

    def snapshot(self, **changes):
        row = dict(phase="early", source="official_odds3t", schema_version=3,
                   odds=[2.0] * 120, deadline_at=self.deadline,
                   captured_at=self.deadline - timedelta(minutes=25),
                   created_at=self.deadline - timedelta(minutes=24))
        row.update(changes)
        return row

    def test_fixed_scope(self):
        self.assertEqual(len(audit.TARGET_RACES), 19)
        self.assertEqual(len(set(audit.TARGET_RACES)), 19)
        self.assertEqual(len(audit.ALL_TICKETS), 120)
        self.assertEqual(len(set(audit.ALL_TICKETS)), 120)
        self.assertTrue(all(r.startswith("20260908_") for r in audit.TARGET_RACES))
        self.assertTrue(all(len(set(t.split("-"))) == 3 for t in audit.ALL_TICKETS))

    def test_ticket_sets(self):
        self.assertTrue(audit.ticket_status(list(audit.ALL_TICKETS))["complete"])
        status = audit.ticket_status(list(audit.ALL_TICKETS[1:]) + [audit.ALL_TICKETS[1]])
        self.assertFalse(status["complete"])
        self.assertEqual(status["missing"], [audit.ALL_TICKETS[0]])
        self.assertEqual(status["duplicates"], 1)
        self.assertFalse(audit.ticket_status(list(audit.ALL_TICKETS) + ["1-1-2"])["complete"])
        self.assertEqual(audit.ticket_status([])["expected"], 120)

    def test_numeric_quality(self):
        self.assertTrue(audit.numeric_quality([1.0] * 120)["valid"])
        for bad in (float("nan"), float("inf"), -float("inf"), 0, -1, None, "bad"):
            with self.subTest(bad=bad):
                values = [1.0] * 120
                values[17] = bad
                self.assertFalse(audit.numeric_quality(values)["valid"])
        self.assertFalse(audit.numeric_quality([1.0] * 119)["valid"])
        self.assertFalse(audit.numeric_quality(None)["valid"])

    def test_candidate_is_not_authentication(self):
        report = audit.review_snapshot(self.snapshot(), self.deadline)
        self.assertEqual(report["status"], "RECORDED_PREDEADLINE_CANDIDATE")
        self.assertEqual(report["provenance"], "stored_metadata_only_not_independently_authenticated")
        result = audit.analyze([], [], [], [dict(self.snapshot(), race_id=self.rid)], {})
        self.assertEqual(result["historical_roi_approval"], "BLOCKED")
        self.assertEqual(result["production_promotion"], "BLOCKED")
        self.assertEqual(result["races"][0]["independent_source_verification"], "NOT_PERFORMED")

    def test_snapshot_time_and_metadata_guards(self):
        cases = [
            (dict(captured_at=self.deadline), "not_proven_before_reference_deadline"),
            (dict(created_at=self.deadline), "created_at_not_proven_before_deadline"),
            (dict(created_at=self.deadline - timedelta(minutes=26)), "created_at_not_proven_before_deadline"),
            (dict(deadline_at=self.deadline + timedelta(minutes=1)), "reference_deadline_mismatch"),
            (dict(captured_at=self.deadline - timedelta(minutes=31)), "outside_early_window"),
            (dict(source="unknown"), "source_not_verified"),
            (dict(schema_version=2), "schema_version_unverified"),
            (dict(odds=[math.nan] * 120), "invalid_odds_vector"),
            (dict(captured_at=self.deadline.replace(tzinfo=None)), "not_proven_before_reference_deadline"),
        ]
        for changes, reason in cases:
            with self.subTest(reason=reason):
                report = audit.review_snapshot(self.snapshot(**changes), self.deadline)
                self.assertEqual(report["status"], "UNVERIFIED")
                self.assertIn(reason, report["reasons"])
        late = self.snapshot(phase="late", captured_at=self.deadline - timedelta(minutes=5),
                             created_at=self.deadline - timedelta(minutes=4))
        self.assertEqual(audit.review_snapshot(late, self.deadline)["status"], "RECORDED_PREDEADLINE_CANDIDATE")

    def test_analyze_never_infers_scratch_or_first_fetch(self):
        result = audit.analyze(
            [dict(race_id=self.rid, deadline_at=self.deadline)],
            [dict(race_id=self.rid, lane=1)],
            [dict(race_id=self.rid, ticket="1-2-3", fetched_at=self.deadline,
                  is_final=False)], [], {})
        self.assertEqual(len(result["races"]), 19)
        row = result["races"][0]
        self.assertEqual(row["entry_status"], "UNVERIFIED")
        self.assertEqual(row["base"]["expected"], 120)
        self.assertEqual(row["predeadline_evidence"], "UNKNOWN")
        self.assertEqual(row["root_cause"], "UNDETERMINED")
        self.assertEqual(row["base_timestamp_semantics"], "current_saved_value_not_first_observation")
        self.assertEqual(row["base_fetched_at_min"], self.deadline.isoformat())

    def test_unzoned_timestamps_are_unknown(self):
        self.assertIsNone(audit.as_time("2026-09-08T08:00:00"))
        self.assertIsNone(audit.iso(self.deadline.replace(tzinfo=None)))
        self.assertEqual(audit.as_time("2026-09-07T23:58:00Z").isoformat(), self.deadline.isoformat())

    def test_date_guard(self):
        with patch.object(sys, "argv", ["audit", "--date", "2026-09-09"]):
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    audit.main()
        self.assertEqual(error.exception.code, 2)

    def fake_database(self, *, missing_schema=False, excess=False, snapshots=True):
        required = {
            "v2_races": ("race_id", "race_date", "deadline_at"),
            "v2_race_entries": ("race_id", "lane"),
            "v2_odds_trifecta": ("race_id", "ticket", "fetched_at", "is_final"),
        }
        if snapshots:
            required["v2_bao_market_shadow_snapshots"] = (
                "race_id", "phase", "captured_at", "created_at", "deadline_at",
                "odds", "source", "schema_version")
        schema = [dict(table_name=table, column_name=col)
                  for table, cols in required.items() for col in cols]
        class Cursor:
            def __init__(self):
                self.commands = []
                self.query = ""
                self.params = ()
                self.limits = []
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, query, params=()):
                self.query, self.params = query, params
                self.commands.append((query, params))
            def fetchmany(self, limit):
                self.limits.append(limit)
                if excess:
                    return [dict()] * (audit.MAX_ROWS + 1)
                if "information_schema.columns" in self.query:
                    return [] if missing_schema else schema
                if "FROM v2_races" in self.query:
                    return [dict(race_id=self_rid, deadline_at=self_deadline)]
                if "FROM v2_race_entries" in self.query:
                    return [dict(race_id=self_rid, lane=n) for n in range(1, 7)]
                if "FROM v2_odds_trifecta" in self.query:
                    return [dict(race_id=self_rid, ticket=t, fetched_at=self_deadline, is_final=False)
                            for t in audit.ALL_TICKETS]
                return []
        class Connection:
            def __init__(self):
                self.cur = Cursor()
                self.rolled_back = False
                self.rollbacks = 0
                self.kwargs = None
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                # psycopg's connection context manager rolls back on exceptions.
                if exc_type is not None:
                    self.rollback()
                return False
            def cursor(self):
                return self.cur
            def rollback(self):
                self.rolled_back = True
                self.rollbacks += 1
        self_rid, self_deadline = self.rid, self.deadline
        conn = Connection()
        def connect(url, **kwargs):
            conn.kwargs = kwargs
            return conn
        fake = types.ModuleType("psycopg")
        fake.connect = connect
        rows = types.ModuleType("psycopg.rows")
        rows.dict_row = object()
        return conn, {"psycopg": fake, "psycopg.rows": rows}

    def test_database_transaction_and_query_bounds(self):
        conn, modules = self.fake_database(missing_schema=True)
        with patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(RuntimeError, "Missing required columns"):
                audit.read_database("mock://database")
        self.assertTrue(conn.rolled_back)
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.cur.commands[0][0], "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        self.assertTrue(all(cmd.lstrip().startswith(("SET ", "SELECT ")) for cmd, _ in conn.cur.commands))
        self.assertTrue(all(not params for _, params in conn.cur.commands))
        self.assertTrue(all(limit <= audit.MAX_ROWS + 1 for limit in conn.cur.limits))
        self.assertFalse(conn.kwargs["autocommit"])

    def test_database_success_is_read_only_and_fixed_scope(self):
        conn, modules = self.fake_database()
        with patch.dict(sys.modules, modules):
            result = audit.read_database("mock://database")
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(result["schema"]["bao_snapshots_available"], True)
        self.assertEqual(result["races"][0]["base"]["complete"], True)
        self.assertEqual(len(result["races"]), 19)
        commands = conn.cur.commands
        self.assertEqual(commands[0][0], "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        self.assertTrue(all(q.lstrip().startswith(("SET ", "SELECT ")) for q, _ in commands))
        data_queries = [(q, p) for q, p in commands if "race_id=ANY(%s)" in q]
        self.assertEqual(len(data_queries), 4)
        for query, params in data_queries:
            self.assertEqual(params[-1], list(audit.TARGET_RACES))
            self.assertTrue(query.lstrip().startswith("SELECT "))
        self.assertEqual(data_queries[0][1][0], audit.TARGET_DATE)
        self.assertTrue(all(limit == audit.MAX_ROWS + 1 for limit in conn.cur.limits))

    def test_optional_snapshot_schema_is_not_fabricated(self):
        conn, modules = self.fake_database(snapshots=False)
        with patch.dict(sys.modules, modules):
            result = audit.read_database("mock://database")
        self.assertEqual(result["schema"]["bao_snapshots_available"], False)
        self.assertEqual(result["races"][0]["predeadline_evidence"], "UNKNOWN")
        self.assertFalse(any("FROM v2_bao_market_shadow_snapshots" in q for q, _ in conn.cur.commands))

    def test_row_limit_is_fail_closed(self):
        conn, modules = self.fake_database(excess=True)
        with patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(RuntimeError, "row limit exceeded"):
                audit.read_database("mock://database")
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.cur.limits, [audit.MAX_ROWS + 1])


if __name__ == "__main__":
    unittest.main()
