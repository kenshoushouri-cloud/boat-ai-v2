"""Offline-only V5 beforeinfo safety regression: NO HTTP GET or DB work.

The actual GitHub pipeline source is loaded with inert dependency stubs. No
live HTTP, real DB driver, scheduler, Railway or BUY path is imported/run.
"""
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class ShouldNotRun(AssertionError):
    pass


class ReachedInjectedCapture(Exception):
    pass


def forbidden(*args, **kwargs):
    raise ShouldNotRun("Unapproved HTTP/DB/start proof side effect")


class FakeSession:
    def __init__(self):
        self.http_gets = 0

    def get(self, *args, **kwargs):
        self.http_gets += 1
        raise ShouldNotRun("HTTP GET executed")


class FakeConnection:
    def __init__(self):
        self.db_transactions = 0
        self.db_cursors = 0

    def transaction(self):
        self.db_transactions += 1
        raise ShouldNotRun("DB transaction executed")

    def cursor(self):
        self.db_cursors += 1
        raise ShouldNotRun("DB cursor executed")


def load_real_pipeline_with_offline_stubs():
    classes = {
        "v5.official_racelist_readback": {"RacelistNotVerified": type("RacelistNotVerified", (RuntimeError,), {}),
                                          "bind_first_write_racelist": forbidden},
        "v5.official_first_write_executor": {"FirstWriteRejected": type("FirstWriteRejected", (RuntimeError,), {}),
                                             "persist_first_http_capture": forbidden},
        "v5.official_http_receipt": {"UnverifiedCapture": type("UnverifiedCapture", (RuntimeError,), {})},
        "v5.beforeinfo_prewrite_gate": {"check_beforeinfo_prewrite": forbidden},
        "v5.official_start_status_provenance": {"classify_predeadline_start_status": forbidden},
        "v5.official_http_transport": {"capture_v5_official_response": forbidden},
    }
    deps = {}
    for dotted, symbols in classes.items():
        fake_module = types.ModuleType(dotted)
        for key, value in symbols.items():
            setattr(fake_module, key, value)
        deps[dotted] = fake_module
    path = Path(__file__).resolve().parents[1] / "v5" / "official_capture_pipeline.py"
    spec = importlib.util.spec_from_file_location("v5._isolated_pre_http_under_test", path)
    result = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, deps):
        spec.loader.exec_module(result)
    return result


class BeforeinfoPreHTTPHardHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pipeline = load_real_pipeline_with_offline_stubs()

    def try_call(self, **overrides):
        session = FakeSession()
        connection = FakeConnection()
        args = {
            "session": session,
            "connection": connection,
            "requested_url": "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=2&jcd=03&hd=20261011",
            "expected_source": "official_beforeinfo",
            "expected_race_id": "20261011_03_02",
            "storage_enabled": True,
        }
        args.update(overrides)
        with self.assertRaises(self.pipeline.CapturePipelineNotReady) as cm:
            self.pipeline.capture_and_store_v5_official_source(**args)
        self.assertEqual(session.http_gets, 0)
        self.assertEqual(connection.db_transactions, 0)
        self.assertEqual(connection.db_cursors, 0)
        return str(cm.exception)

    def test_enabled_beforeinfo_hard_holds_before_all_io(self):
        self.assertEqual(self.try_call(), "BEFOREINFO_PRE_HTTP_HARD_HOLD_NO_AUTHENTICATED_POSITIVE_START")

    def test_caller_positive_roster_does_not_bypass(self):
        result = self.try_call(racelist_evidence={
            "all_six_active_confirmed": True, "first_write_confirmed": True,
            "beforeinfo_prewrite_eligible": True, "forward_eligible": True,
        })
        self.assertIn("PRE_HTTP_HARD_HOLD", result)

    def test_even_missing_http_and_db_objects_cannot_trigger_io(self):
        result = self.try_call(session=None, connection=None)
        self.assertIn("PRE_HTTP_HARD_HOLD", result)

    def test_disabled_storage_still_denies_without_io(self):
        self.assertEqual(self.try_call(storage_enabled=False), "V5_STORAGE_NOT_ENABLED")

    def test_wrong_or_missing_race_values_never_trigger_http(self):
        for race in (None, "20261011_03_03", "invalid", ""):
            with self.subTest(race=race):
                self.assertIn("PRE_HTTP_HARD_HOLD", self.try_call(expected_race_id=race))

    def test_non_beforeinfo_sources_still_reach_collector_only(self):
        for source in ("official_racelist", "official_k_file"):
            with self.subTest(source=source):
                session, connection = FakeSession(), FakeConnection()
                mocked_transport = Mock(side_effect=ReachedInjectedCapture)
                with patch.object(self.pipeline, "capture_v5_official_response", mocked_transport):
                    with self.assertRaises(ReachedInjectedCapture):
                        self.pipeline.capture_and_store_v5_official_source(
                            session=session, connection=connection,
                            requested_url="synthetic-not-requested", expected_source=source,
                            expected_race_id=None, storage_enabled=True,
                        )
                mocked_transport.assert_called_once()
                self.assertEqual(session.http_gets, 0)
                self.assertEqual(connection.db_transactions, 0)
                self.assertEqual(connection.db_cursors, 0)


if __name__ == "__main__":
    unittest.main()
