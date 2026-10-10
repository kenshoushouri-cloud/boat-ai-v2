# -*- coding: utf-8 -*-
"""V5 capture→real PostgreSQL integration, fake HTTP only.

Never use Railway, DATABASE_URL or external HTTP; requires a disposable GitHub
Actions Postgres 16 service with separate INSERT+SELECT-only writer.
"""
from __future__ import annotations

import hashlib
import os
import unittest
from datetime import datetime

import psycopg
from psycopg.errors import InsufficientPrivilege

from v5.official_capture_pipeline import (
    CapturePipelineNotReady,
    capture_and_store_v5_official_source,
)
from v5.official_first_write_storage import DDL
from v5_beforeinfo_test_fixtures import six_boat_html, racelist_evidence, DEADLINE, CUTOFF
from test_v5_official_racelist_readback import make_html

BEFORE4 = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=4&jcd=09&hd=20261010"
BEFORE5 = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=5&jcd=09&hd=20261010"
RACELIST4 = BEFORE4.replace("beforeinfo","racelist")
RACELIST5 = BEFORE5.replace("beforeinfo","racelist")
K_FILE = "https://www1.mbrace.or.jp/od2/K/202610/k261009.lzh"
TIME_START = "2026-10-10T11:49:59+09:00"
TIME_DONE = "2026-10-10T11:50:00+09:00"


class SyntheticResponse:
    def __init__(self, url: str, body: bytes, status=200):
        self.url = url
        self.body = body
        self.status_code = status
        self.history = []
        self.headers = {"Content-Length": str(len(body))}
        self.closed = False

    def iter_content(self, *, chunk_size):
        yield self.body

    def close(self):
        self.closed = True


class SyntheticSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def synthetic_clock():
    ticks = iter((TIME_START, TIME_DONE))
    return lambda: next(ticks)


class TestV5CapturePipelinePostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if (os.environ.get("GITHUB_ACTIONS") != "true"
                or os.environ.get("V5_CI_EPHEMERAL_PG") != "YES"
                or os.environ.get("DATABASE_URL")):
            raise RuntimeError("GITHUB_EPHEMERAL_POSTGRES_ONLY")
        cls.admin = psycopg.connect(
            host="127.0.0.1", port=5432, dbname="v5_ephemeral_ci",
            user="postgres", password="ci-local-postgres-only",
            autocommit=True, connect_timeout=5,
        )
        try:
            cls.admin.execute(DDL)
            cls.admin.execute(
                "REVOKE ALL ON v5_official_source_first_capture FROM PUBLIC"
            )
            cls.admin.execute(
                "CREATE ROLE v5_pipeline_ci_writer LOGIN PASSWORD "
                "'ci-local-synthetic-not-production'"
            )
            cls.admin.execute(
                "GRANT USAGE ON SCHEMA public TO v5_pipeline_ci_writer"
            )
            cls.admin.execute(
                "GRANT SELECT, INSERT ON v5_official_source_first_capture "
                "TO v5_pipeline_ci_writer"
            )
            cls.writer = psycopg.connect(
                host="127.0.0.1", port=5432, dbname="v5_ephemeral_ci",
                user="v5_pipeline_ci_writer",
                password="ci-local-synthetic-not-production",
                autocommit=True, connect_timeout=5,
            )
        except BaseException:
            cls.admin.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.writer.close()
        cls.admin.close()

    def setUp(self):
        self.admin.execute("TRUNCATE v5_official_source_first_capture")

    def count_rows(self):
        return self.admin.execute(
            "SELECT count(*) FROM v5_official_source_first_capture"
        ).fetchone()[0]

    def run_capture(self, *, url=RACELIST4, body=b"synthetic-six-entries",
                    status=200, enabled=True, race="20261010_09_04",
                    source="official_racelist", roster_override=None):
        raw = six_boat_html(variation=body.hex()) if source == "official_beforeinfo" else body
        reply = SyntheticResponse(url, raw, status=status)
        session = SyntheticSession(reply)
        roster = racelist_evidence()
        if race == "20261010_09_05":
            roster["race_id"] = race
            roster["source_url"] = roster["source_url"].replace("rno=4", "rno=5")
        result = capture_and_store_v5_official_source(
            session=session, connection=self.writer,
            requested_url=url, expected_source=source,
            expected_race_id=race, storage_enabled=enabled,
            clock=synthetic_clock(),
            official_deadline_at=DEADLINE,
            prediction_cutoff_at=CUTOFF,
            racelist_evidence=roster if roster_override is None else roster_override,
        )
        return result, session, reply

    def test_initial_capture_commits_exact_original_bytes_and_sha(self):
        raw = b"synthetic-\x00\xff-six-boats"
        result, session, reply = self.run_capture(body=raw)
        self.assertEqual(result["status"], "STORED_SOURCE_CONSISTENT_FORWARD_UNVERIFIED")
        self.assertTrue(result["inserted_this_attempt"])
        self.assertFalse(result["forward_eligible"])
        self.assertFalse(result["first_write_confirmed"])
        self.assertIsNone(result["first_observed_at"])
        self.assertTrue(reply.closed)
        self.assertEqual(len(session.calls), 1)
        saved = self.admin.execute(
            "SELECT raw_bytes, raw_sha256, source_url, response_completed_at "
            "FROM v5_official_source_first_capture",
        ).fetchone()
        self.assertEqual(saved[0], raw)
        self.assertEqual(saved[1], hashlib.sha256(raw).hexdigest())
        self.assertEqual(saved[2], RACELIST4)
        self.assertEqual(saved[3], datetime.fromisoformat(TIME_DONE))
        self.assertEqual(self.count_rows(), 1)

    def test_identical_repeat_does_not_change_first_row(self):
        self.run_capture()
        frozen = self.admin.execute(
            "SELECT stored_at, raw_bytes, response_completed_at "
            "FROM v5_official_source_first_capture"
        ).fetchone()
        result, _, _ = self.run_capture()
        self.assertFalse(result["inserted_this_attempt"])
        self.assertEqual(result["storage_status"], "EXISTING_IDENTICAL_FIRST_CAPTURE")
        self.assertEqual(frozen, self.admin.execute(
            "SELECT stored_at, raw_bytes, response_completed_at "
            "FROM v5_official_source_first_capture"
        ).fetchone())
        self.assertEqual(self.count_rows(), 1)

    def test_changed_source_body_conflicts_and_rolls_back(self):
        self.run_capture(body=b"first response")
        with self.assertRaisesRegex(
            CapturePipelineNotReady, "^V5_CAPTURE_OR_STORAGE_NOT_VERIFIED$"
        ):
            self.run_capture(body=b"page changed after initial fetch")
        self.assertEqual(self.count_rows(), 1)
        original = self.admin.execute(
            "SELECT raw_bytes FROM v5_official_source_first_capture"
        ).fetchone()[0]
        self.assertEqual(original, b"first response")

    def test_corrupted_first_row_refuses_new_match(self):
        self.run_capture(body=b"original")
        self.admin.execute(
            "UPDATE v5_official_source_first_capture SET raw_bytes=%s",
            (b"tampered-owner",),
        )
        with self.assertRaisesRegex(
            CapturePipelineNotReady, "^V5_CAPTURE_OR_STORAGE_NOT_VERIFIED$"
        ):
            self.run_capture(body=b"original")
        self.assertEqual(self.count_rows(), 1)

    def test_two_independent_races_keep_distinct_snapshots(self):
        self.run_capture(body=b"race-four")
        second, _, _ = self.run_capture(
            url=RACELIST5, body=b"race-five", race="20261010_09_05"
        )
        self.assertTrue(second["inserted_this_attempt"])
        self.assertEqual(self.count_rows(), 2)

    def test_daily_k_file_never_fabricates_single_race(self):
        result, _, _ = self.run_capture(
            url=K_FILE, body=b"synthetic-K-archive",
            race=None, source="official_k_file",
        )
        self.assertEqual(result["resource_key"], "official_k_file:261009")
        self.assertIsNone(self.admin.execute(
            "SELECT race_id FROM v5_official_source_first_capture"
        ).fetchone()[0])

    def test_bad_http_status_never_commits(self):
        with self.assertRaisesRegex(
            CapturePipelineNotReady, "^V5_CAPTURE_OR_STORAGE_NOT_VERIFIED$"
        ):
            self.run_capture(status=503)
        self.assertEqual(self.count_rows(), 0)

    def test_disabled_pipeline_does_not_fetch_or_write(self):
        response = SyntheticResponse(BEFORE4, b"synthetic")
        session = SyntheticSession(response)
        with self.assertRaisesRegex(CapturePipelineNotReady, "^V5_STORAGE_NOT_ENABLED$"):
            capture_and_store_v5_official_source(
                session=session, connection=self.writer, requested_url=BEFORE4,
                expected_source="official_beforeinfo",
                expected_race_id="20261010_09_04",
                clock=synthetic_clock(),
            )
        self.assertEqual(session.calls, [])
        self.assertEqual(self.count_rows(), 0)

    def test_writer_lacks_update_delete_privileges(self):
        self.run_capture()
        with self.assertRaises(InsufficientPrivilege):
            self.writer.execute(
                "UPDATE v5_official_source_first_capture SET raw_bytes=%s",
                (b"not-allowed",),
            )
        with self.assertRaises(InsufficientPrivilege):
            self.writer.execute("DELETE FROM v5_official_source_first_capture")
        self.assertEqual(self.count_rows(), 1)


    def test_beforeinfo_forged_active_flags_never_persist(self):
        forged = racelist_evidence()
        forged["active_verified"]=True
        forged["all_active_verified"]=True
        with self.assertRaisesRegex(
            CapturePipelineNotReady, "^V5_CAPTURE_OR_STORAGE_NOT_VERIFIED$"
        ):
            self.run_capture(
                url=BEFORE4, source="official_beforeinfo",
                roster_override=forged,
            )
        self.assertEqual(self.count_rows(),0)

    def test_beforeinfo_with_original_racelist_row_cannot_assume_all_active(self):
        self.run_capture(url=RACELIST4, body=make_html())
        forged = racelist_evidence()
        forged["all_active_verified"]=True
        with self.assertRaisesRegex(
            CapturePipelineNotReady, "^BEFOREINFO_PREWRITE_DENIED:ACTIVE_START_STATUS_NOT_PROVEN$"
        ):
            self.run_capture(
                url=BEFORE4, source="official_beforeinfo",
                roster_override=forged,
            )
        self.assertEqual(self.count_rows(),1)
        key = self.admin.execute(
            "SELECT resource_key FROM v5_official_source_first_capture"
        ).fetchone()[0]
        self.assertEqual(key,"official_racelist:20261010_09_04")

    def test_beforeinfo_corrupted_racelist_storage_fails_before_insert(self):
        self.run_capture(url=RACELIST4, body=make_html())
        self.admin.execute(
            "UPDATE v5_official_source_first_capture SET raw_bytes=%s",
            (b"tampered-digest",),
        )
        with self.assertRaisesRegex(
            CapturePipelineNotReady, "^V5_CAPTURE_OR_STORAGE_NOT_VERIFIED$"
        ):
            self.run_capture(url=BEFORE4, source="official_beforeinfo")
        self.assertEqual(self.count_rows(),1)


if __name__ == "__main__":
    unittest.main()
