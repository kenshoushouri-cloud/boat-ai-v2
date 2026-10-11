"""Pure synthetic tests; no live DB or psql process."""
import unittest
from datetime import date
from v5.offline_catalog_smoke_gate import (
    REQUIRED, INDEX_PREFIX, HEADERS, audit_catalog_psql_output,
    first_day_smoke_contract, check_smoke_measurements,
)


def transcript(overrides=None):
    overrides = overrides or {}
    lines = [HEADERS[0]]
    for table, attrs in REQUIRED.items():
        for name, types in attrs.items():
            t = next(iter(sorted(types)))
            if t == "timestamp": t = "timestamptz"
            verdict = "PRESENT_TYPE_REVIEW"
            if (table, name) in overrides:
                t, verdict = overrides[(table, name)]
            lines.append(f"{table}|{name}|{t}|{t}|YES|{verdict}")
    lines.extend(["(20 rows)", HEADERS[1]])
    for table, prefix in INDEX_PREFIX.items():
        status = overrides.get((table, "index"), "t")
        lines.append(f"{table}|{{{','.join(prefix)}}}|{status}|idx_{table}")
    lines.extend(["(4 rows)", HEADERS[2],
                  "sample_archive|readonly_role|on|2s|t|t|t|t", "(1 row)"])
    return "\n".join(lines) + "\n"


class CatalogGateTests(unittest.TestCase):
    def test_valid_shape_still_cannot_authenticate_real_db(self):
        x = audit_catalog_psql_output(transcript())
        self.assertEqual(x.status, "CATALOG_SHAPE_OK_SOURCE_NOT_AUTHENTICATED")
        self.assertEqual((x.checked_columns, x.checked_indexes), (20, 4))
        self.assertFalse(x.live_schema_verified)
        self.assertFalse(x.smoke_authorized)
        self.assertFalse(x.buy_eligible)

    def test_actual_grade_schema_uses_textual_column(self):
        self.assertNotIn("racer_class", REQUIRED["v2_race_entries"])
        self.assertEqual(REQUIRED["v2_race_entries"]["racer_class_text"],
                         frozenset(("text", "varchar")))
        fake = transcript({("v2_race_entries", "racer_class_text"):
                           ("int4", "PRESENT_TYPE_REVIEW")})
        result = audit_catalog_psql_output(fake)
        self.assertIn("MISSING_OR_UNSAFE_COLUMN_TYPE:v2_race_entries.racer_class_text",
                      result.reasons)
        self.assertFalse(result.smoke_authorized)

    def test_missing_column_holds(self):
        x = audit_catalog_psql_output(transcript({("v2_races", "race_id"): ("", "MISSING")}))
        self.assertEqual(x.status, "HOLD_CATALOG_CONTRACT")
        self.assertIn("MISSING_OR_UNSAFE_COLUMN_TYPE:v2_races.race_id", x.reasons)

    def test_naive_deadline_not_silently_accepted(self):
        x = audit_catalog_psql_output(transcript({("v2_races", "deadline_at"): ("timestamp", "PRESENT_TYPE_REVIEW")}))
        self.assertIn("MISSING_OR_UNSAFE_COLUMN_TYPE:v2_races.deadline_at", x.reasons)

    def test_missing_index_holds(self):
        x = audit_catalog_psql_output(transcript({("v2_race_entries", "index"): "f"}))
        self.assertIn("INDEX_LEFT_PREFIX_UNVERIFIED:v2_race_entries", x.reasons)

    def test_transaction_writeable_holds(self):
        x = audit_catalog_psql_output(transcript().replace("|on|2s|", "|off|2s|"))
        self.assertIn("TRANSACTION_NOT_READ_ONLY", x.reasons)

    def test_select_denied_holds(self):
        x = audit_catalog_psql_output(transcript().replace("|t|t|t|t\n", "|t|t|f|t\n"))
        self.assertIn("REQUIRED_SELECT_PRIVILEGE_MISSING", x.reasons)

    def test_timeout_wrong_holds(self):
        x = audit_catalog_psql_output(transcript().replace("|on|2s|", "|on|10s|"))
        self.assertIn("STATEMENT_TIMEOUT_NOT_2S", x.reasons)

    def test_truncated_or_extra_output_holds(self):
        for payload in (transcript()[:500], transcript()+"INJECTED\n", transcript()+"x"*12000):
            self.assertEqual(audit_catalog_psql_output(payload).status, "HOLD_CATALOG_FORMAT")

    def test_one_day_cap_is_not_auth(self):
        c = first_day_smoke_contract(date(2026, 5, 1))
        self.assertEqual((c.max_inventory_rows, c.max_lane_rows, c.max_result_rows, c.max_total_bytes),
                         (400, 2400, 400, 4_000_000))
        status, reasons = check_smoke_measurements(c, 120, 720, 120, 2_000_000)
        self.assertEqual(status, "SMOKE_COUNTS_WITHIN_CAP_UNVERIFIED")
        self.assertFalse(reasons)
        self.assertFalse(c.database_read_authorized)

    def test_smoke_overflow_holds(self):
        c = first_day_smoke_contract(date(2026, 5, 1))
        status, reasons = check_smoke_measurements(c, 401, 2401, 401, 4_000_001)
        self.assertEqual(status, "HOLD_SMOKE_LIMIT_OR_COVERAGE")
        self.assertIn("TRANSFER_BYTES_OVER_LIMIT", reasons)

    def test_smoke_missing_duplicate_rows_holds(self):
        c = first_day_smoke_contract(date(2026, 5, 1))
        for counts in ((2, 11, 2, 500), (2, 13, 2, 500), (2, 12, 1, 500)):
            self.assertEqual(check_smoke_measurements(c, *counts)[0],
                             "HOLD_SMOKE_LIMIT_OR_COVERAGE")

    def test_smoke_invalid_types_rejected(self):
        c = first_day_smoke_contract(date(2026, 5, 1))
        for counts in ((True, 6, 1, 1), (1, -1, 1, 50), (1, 6, 1, -1)):
            with self.assertRaises(ValueError): check_smoke_measurements(c, *counts)
        with self.assertRaises(ValueError): first_day_smoke_contract(date(2025, 6, 30))


if __name__ == "__main__":
    unittest.main()
