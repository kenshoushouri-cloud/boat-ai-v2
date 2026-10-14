#!/usr/bin/env python3
"""V5 readback fail-closed regression; no production imports, HTTP, DB, or I/O.

Extract exactly the reviewed pure function from the SHA-pinned production source
and run it using synthetic rows. PASS never proves origin, predeadline, or BUY.
"""
from __future__ import annotations

import __future__
import ast
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name("official_first_write_storage.py")
SOURCE_BLOB = "d32bc29b4a5710f347b3b03ed498db54504f94be"


class UnverifiedCapture(ValueError):
    pass


def _aware_dt(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise UnverifiedCapture("UNZONED_CLOCK")
    return value


class ReadbackContractOffline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SOURCE.read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
        if actual != SOURCE_BLOB:
            raise AssertionError("REVIEWED_SOURCE_BLOB_CHANGED")
        tree = ast.parse(source, filename=str(SOURCE))
        funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "verify_first_write_readback"]
        if len(funcs) != 1:
            raise AssertionError("READBACK_FUNCTION_NOT_UNIQUE")
        scope = {"Mapping": Mapping, "datetime": datetime, "hashlib": hashlib,
                 "_aware_dt": _aware_dt, "UnverifiedCapture": UnverifiedCapture}
        unit = ast.Module(body=funcs, type_ignores=[])
        exec(compile(unit, str(SOURCE), "exec",
                     flags=__future__.annotations.compiler_flag), scope)
        cls.check = staticmethod(scope["verify_first_write_readback"])

    def setUp(self):
        start = datetime(2026, 10, 14, 15, 0, tzinfo=timezone(timedelta(hours=9)))
        end = start + timedelta(seconds=1)
        self.raw = b"SYNTHETIC_OFFLINE_FAKE_HTML"
        digest = hashlib.sha256(self.raw).hexdigest()
        self.params = ("official_racelist:20261014_24_01", "official_racelist",
                       "20261014_24_01", "https://synthetic.example/mock",
                       start, end, self.raw, digest)
        self.plan = {"params": self.params}
        self.row = dict(zip(("resource_key", "source_kind", "race_id", "source_url",
                             "request_started_at", "response_completed_at", "raw_bytes",
                             "raw_sha256"), self.params))
        self.row["stored_at"] = end + timedelta(seconds=1)

    def verify(self, inserted=True, plan=None, row=None):
        return self.check(self.plan if plan is None else plan,
                          self.row if row is None else row,
                          inserted_this_attempt=inserted)

    def assert_denied(self, code, **changes):
        outcome = self.verify(**changes)
        self.assertEqual(outcome["status"], code)
        self.assertIs(outcome["storage_consistent"], False)
        self.assertIs(outcome["forward_eligible"], False)
        self.assertIs(outcome["first_write_confirmed"], False)
        self.assertIsNone(outcome["first_observed_at"])

    def test_first_insert_matching_still_not_forward(self):
        o = self.verify(True)
        self.assertEqual(o["status"], "INSERTED_AND_READBACK_MATCH_SOURCE_UNVERIFIED")
        self.assertIs(o["storage_consistent"], True)
        self.assertIs(o["forward_eligible"], False)
        self.assertIs(o["first_write_confirmed"], False)
        self.assertIsNone(o["first_observed_at"])

    def test_duplicate_matching_still_not_forward(self):
        o = self.verify(False)
        self.assertEqual(o["status"], "EXISTING_IDENTICAL_FIRST_CAPTURE")
        self.assertIs(o["storage_consistent"], True)
        self.assertIs(o["forward_eligible"], False)
        self.assertIsNone(o["first_observed_at"])

    def test_memoryview_readback_allowed_but_not_forward(self):
        self.row["raw_bytes"] = memoryview(self.raw)
        self.assertIs(self.verify()["forward_eligible"], False)
        self.assertIs(self.verify()["storage_consistent"], True)

    def test_missing_plan(self):
        self.assert_denied("INVALID_STORAGE_PLAN", plan={})

    def test_bad_param_tuple(self):
        self.assert_denied("INVALID_STORAGE_PLAN", plan={"params": self.params[:-1]})

    def test_unverified_insert_outcome_none(self):
        self.assert_denied("INSERT_OUTCOME_UNVERIFIED", inserted=None)

    def test_unverified_insert_outcome_integer(self):
        self.assert_denied("INSERT_OUTCOME_UNVERIFIED", inserted=1)

    def test_missing_frozen_row(self):
        self.assert_denied("FIRST_WRITE_READBACK_MISSING", row=[])

    def test_missing_stored_at(self):
        self.row.pop("stored_at")
        self.assert_denied("DB_STORED_AT_MISSING_OR_INVALID")

    def test_unzoned_stored_at(self):
        self.row["stored_at"] = datetime(2026, 10, 14, 15, 0)
        self.assert_denied("DB_STORED_AT_MISSING_OR_INVALID")

    def test_stored_at_before_response_completion(self):
        self.row["stored_at"] = self.params[5] - timedelta(microseconds=1)
        self.assert_denied("DB_STORED_AT_BEFORE_RESPONSE_COMPLETION")

    def test_missing_bytes(self):
        self.row.pop("raw_bytes")
        self.assert_denied("FROZEN_RAW_BYTES_UNAVAILABLE")

    def test_tampered_content_same_size(self):
        self.row["raw_bytes"] = b"X" + self.raw[1:]
        self.assert_denied("FIRST_WRITE_COLLISION_OR_TAMPERING")

    def test_tampered_hash(self):
        self.row["raw_sha256"] = "0" * 64
        self.assert_denied("FIRST_WRITE_COLLISION_OR_TAMPERING")

    def test_wrong_resource_key(self):
        self.row["resource_key"] = "different"
        self.assert_denied("FIRST_WRITE_COLLISION_OR_TAMPERING")

    def test_wrong_race_id(self):
        self.row["race_id"] = "different"
        self.assert_denied("FIRST_WRITE_COLLISION_OR_TAMPERING")

    def test_wrong_source_url(self):
        self.row["source_url"] = "https://synthetic.example/other"
        self.assert_denied("FIRST_WRITE_COLLISION_OR_TAMPERING")

    def test_clock_mismatch(self):
        self.row["request_started_at"] += timedelta(seconds=1)
        self.assert_denied("FIRST_WRITE_COLLISION_OR_TAMPERING")

    def test_forged_plan_claim_does_not_promote_forward(self):
        self.plan["forward_eligible"] = True
        self.plan["first_observed_at"] = "2026-10-14T15:00:01+09:00"
        o = self.verify()
        self.assertIs(o["forward_eligible"], False)
        self.assertIsNone(o["first_observed_at"])
        # Plan-level fake claims must be rejected by the EXECUTOR's separate gate.
        # This readback function only verifies bytes and times, never that gate.


if __name__ == "__main__":
    unittest.main()
