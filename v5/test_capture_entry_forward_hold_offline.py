#!/usr/bin/env python3
"""Offline unit tests for the exact V5 capture entrypoint, with zero live I/O.

The original function AST is executed in an isolated namespace with fake
transport and storage functions; imports/production modules are NOT executed.
Changing the reviewed source blob fails closed until explicitly re-audited.
"""
from __future__ import annotations

import __future__
import ast
import hashlib
from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name("official_capture_pipeline.py")
REVIEWED_BLOB_SHA = "0831dcfc768ef2598f97f1615b94bed3b3eec2a8"


class Rejected(RuntimeError):
    pass


class FakeSession:
    def get(self, *args, **kwargs):
        raise AssertionError("REAL_OR_MOCK_HTTP_SHOULD_NOT_BE_CALLED")


class FakeConnection:
    def transaction(self):
        raise AssertionError("DB_TRANSACTION_SHOULD_NOT_BE_CALLED")

    def cursor(self):
        raise AssertionError("DB_CURSOR_SHOULD_NOT_BE_CALLED")


class CaptureEntrypointOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = SOURCE.read_bytes()
        git_sha = hashlib.sha1(
            b"blob " + str(len(data)).encode() + b"\0" + data
        ).hexdigest()
        if git_sha != REVIEWED_BLOB_SHA:
            raise AssertionError("CAPTURE_ENTRY_SOURCE_CHANGED_REVIEW_REQUIRED")
        cls.module_ast = ast.parse(data, filename=str(SOURCE))

    def setUp(self):
        self.calls = {"transport": 0, "store": 0, "roster": 0, "start": 0}
        self.proposal = {
            "status": "HTTP_OBSERVED_STORAGE_NOT_EXECUTED",
            "forward_eligible": False,
            "first_observed_at": None,
            "receipt_proposal": {
                "source": "official_racelist",
                "response_completed_at": "2026-10-14T09:00:00+09:00",
                "raw_sha256": "synthetic-no-source-bytes",
            },
            "storage_plan": {"synthetic": True},
        }
        self.stored = {
            "status": "INSERTED_AND_READBACK_MATCH_SOURCE_UNVERIFIED",
            "storage_consistent": True,
            "forward_eligible": False,
            "first_observed_at": None,
            "first_write_confirmed": False,
            "resource_key": "synthetic-only",
            "inserted_this_attempt": True,
        }
        def capture(**kwargs):
            self.calls["transport"] += 1
            return self.proposal

        def persist(connection, plan):
            self.calls["store"] += 1
            return self.stored

        def roster(*args, **kwargs):
            self.calls["roster"] += 1
            raise AssertionError("ROSTER_SELECT_MUST_NOT_RUN")

        def start(*args, **kwargs):
            self.calls["start"] += 1
            raise AssertionError("START_CLASSIFIER_MUST_NOT_RUN")

        fn = [n for n in self.module_ast.body if (
            isinstance(n, ast.FunctionDef)
            and n.name == "capture_and_store_v5_official_source"
        )]
        self.assertEqual(len(fn), 1)
        module = ast.Module(body=fn, type_ignores=[])
        ns = {
            "CapturePipelineNotReady": Rejected,
            "FirstWriteRejected": Rejected,
            "UnverifiedCapture": Rejected,
            "RacelistNotVerified": Rejected,
            "capture_v5_official_response": capture,
            "persist_first_http_capture": persist,
            "bind_first_write_racelist": roster,
            "classify_predeadline_start_status": start,
            "check_beforeinfo_prewrite": start,
        }
        exec(compile(module, str(SOURCE), "exec",
                     flags=__future__.annotations.compiler_flag), ns)
        self.run_entry = ns["capture_and_store_v5_official_source"]

    def invoke(self, source="official_racelist", **kwargs):
        args = {
            "session": FakeSession(),
            "connection": FakeConnection(),
            "requested_url": "https://invalid.example/synthetic-no-http",
            "expected_source": source,
            "expected_race_id": "SYNTHETIC",
            "storage_enabled": True,
        }
        args.update(kwargs)
        return self.run_entry(**args)

    def denied(self, message, source="official_racelist", **kwargs):
        with self.assertRaisesRegex(Rejected, message):
            self.invoke(source, **kwargs)

    def test_beforeinfo_hard_hold_pre_http_and_pre_db(self):
        self.denied("BEFOREINFO_PRE_HTTP_HARD_HOLD", "official_beforeinfo")
        self.assertEqual(self.calls, dict.fromkeys(self.calls, 0))

    def test_beforeinfo_ignores_fake_positive_roster(self):
        self.denied(
            "BEFOREINFO_PRE_HTTP_HARD_HOLD", "official_beforeinfo",
            racelist_evidence={"all_six_active_confirmed": True,
                               "forward_eligible": True},
        )
        self.assertEqual(self.calls, dict.fromkeys(self.calls, 0))

    def test_beforeinfo_hard_hold_precedes_bad_dependencies(self):
        self.denied(
            "BEFOREINFO_PRE_HTTP_HARD_HOLD", "official_beforeinfo",
            session=None, connection=None,
        )
        self.assertEqual(self.calls, dict.fromkeys(self.calls, 0))

    def test_storage_disabled_precedes_all_calls(self):
        self.denied("V5_STORAGE_NOT_ENABLED",
                    "official_beforeinfo", storage_enabled=False)
        self.assertEqual(self.calls, dict.fromkeys(self.calls, 0))

    def test_missing_session_denied(self):
        self.denied("EXPLICIT_HTTP_SESSION_REQUIRED", session=None)
        self.assertEqual(self.calls, dict.fromkeys(self.calls, 0))

    def test_missing_connection_denied(self):
        self.denied("EXPLICIT_ISOLATED_DB_CONNECTION_REQUIRED", connection=None)
        self.assertEqual(self.calls, dict.fromkeys(self.calls, 0))

    def test_racelist_synthetic_consistent_save_still_nonforward(self):
        result = self.invoke()
        self.assertEqual((self.calls["transport"], self.calls["store"]), (1, 1))
        self.assertFalse(result["forward_eligible"])
        self.assertFalse(result["first_write_confirmed"])
        self.assertIsNone(result["first_observed_at"])
        self.assertEqual(result["status"],
                         "STORED_SOURCE_CONSISTENT_FORWARD_UNVERIFIED")
        self.assertEqual(self.calls["roster"], 0)

    def test_k_file_synthetic_consistent_save_still_nonforward(self):
        self.proposal["receipt_proposal"]["source"] = "official_k_file"
        result = self.invoke(source="official_k_file", expected_race_id=None)
        self.assertFalse(result["forward_eligible"])
        self.assertFalse(result["first_write_confirmed"])
        self.assertEqual(self.calls["store"], 1)

    def test_proposal_forward_true_rejected_before_storage(self):
        self.proposal["forward_eligible"] = True
        self.denied("UNVERIFIED_HTTP_CAPTURE_PROPOSAL")
        self.assertEqual(self.calls["store"], 0)

    def test_proposal_fake_earliest_observation_rejected(self):
        self.proposal["first_observed_at"] = "forged-clock"
        self.denied("UNVERIFIED_HTTP_CAPTURE_PROPOSAL")
        self.assertEqual(self.calls["store"], 0)

    def test_bad_proposal_status_rejected(self):
        self.proposal["status"] = "FORGED_STORAGE_OK"
        self.denied("UNVERIFIED_HTTP_CAPTURE_PROPOSAL")
        self.assertEqual(self.calls["store"], 0)

    def test_persist_forward_true_rejected(self):
        self.stored["forward_eligible"] = True
        self.denied("UNVERIFIED_FIRST_WRITE_READBACK")

    def test_persist_first_write_claim_rejected(self):
        self.stored["first_write_confirmed"] = True
        self.denied("UNVERIFIED_FIRST_WRITE_READBACK")

    def test_persist_first_observed_claim_rejected(self):
        self.stored["first_observed_at"] = "forged-clock"
        self.denied("UNVERIFIED_FIRST_WRITE_READBACK")

    def test_persist_inconsistent_rejected(self):
        self.stored["storage_consistent"] = False
        self.denied("UNVERIFIED_FIRST_WRITE_READBACK")

    def test_legacy_roster_input_ignored_on_racelist(self):
        result = self.invoke(racelist_evidence={"all_six_active_confirmed": True})
        self.assertFalse(result["forward_eligible"])
        self.assertEqual(self.calls["roster"], 0)


if __name__ == "__main__":
    unittest.main()
