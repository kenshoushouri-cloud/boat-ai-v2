# -*- coding: utf-8 -*-
"""Real SQL in a GitHub Actions EPHEMERAL localhost Postgres container ONLY.

Never read DATABASE_URL, Railway variables, production credentials, or perform
HTTP requests. Test role is INSERT+SELECT, not table owner; owner can still
alter data, so these checks do NOT assert irreversible audit provenance.
"""
from __future__ import annotations

import hashlib
import os
import unittest

import psycopg
from psycopg.errors import InsufficientPrivilege

from v5.official_first_write_executor import (
    FirstWriteRejected, persist_first_http_capture,
)
from v5.official_first_write_storage import (
    DDL, TABLE, prepare_first_write_storage,
)
from v5.official_http_receipt import prepare_official_http_receipt

RACE1 = "20261010_09_04"
RACE2 = "20261010_09_05"
BASE = "https://www.boatrace.jp/owpc/pc/race/"
BEFORE1 = BASE + "beforeinfo?rno=4&jcd=09&hd=20261010"
BEFORE2 = BASE + "beforeinfo?rno=5&jcd=09&hd=20261010"
K_FILE = "https://www1.mbrace.or.jp/od2/K/202610/k261009.lzh"
START = "2026-10-10T11:49:59+09:00"
END = "2026-10-10T11:50:00+09:00"
WRITER = "v5_ephemeral_writer"
WRITER_PASS = "ci-local-synthetic-not-production"


def plan_for(url: str, body: bytes, race: str | None):
    kind = "official_k_file" if url == K_FILE else "official_beforeinfo"
    receipt = prepare_official_http_receipt(
        requested_url=url, final_url=url, expected_source=kind,
        http_status=200, response_body=body,
        request_started_at=START, response_completed_at=END,
    )
    return prepare_first_write_storage(receipt, expected_race_id=race)


class TestV5FirstWriteRealPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Explicit safety fence. Never allow a user-supplied DATABASE_URL.
        if (os.environ.get("V5_CI_EPHEMERAL_PG") != "YES"
                or os.environ.get("GITHUB_ACTIONS") != "true"):
            raise RuntimeError("EPHEMERAL_GITHUB_ACTIONS_POSTGRES_ONLY")
        cls.admin = psycopg.connect(
            host="127.0.0.1", port=5432, dbname="v5_ephemeral_ci",
            user="postgres", password="ci-local-postgres-only",
            connect_timeout=5, autocommit=True,
        )
        try:
            cls.admin.execute(DDL)
            cls.admin.execute("REVOKE ALL ON TABLE v5_official_source_first_capture FROM PUBLIC")
            cls.admin.execute(
                "CREATE ROLE v5_ephemeral_writer LOGIN PASSWORD "
                "'ci-local-synthetic-not-production'"
            )
            cls.admin.execute("GRANT USAGE ON SCHEMA public TO v5_ephemeral_writer")
            cls.admin.execute(
                "GRANT INSERT, SELECT ON TABLE v5_official_source_first_capture "
                "TO v5_ephemeral_writer"
            )
            cls.writer = psycopg.connect(
                host="127.0.0.1", port=5432, dbname="v5_ephemeral_ci",
                user=WRITER, password=WRITER_PASS,
                connect_timeout=5, autocommit=True,
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

    def count(self) -> int:
        return self.admin.execute(
            "SELECT count(*) FROM v5_official_source_first_capture"
        ).fetchone()[0]

    def test_create_table_has_persistent_binary_and_unique_resource(self):
        self.assertEqual(self.count(), 0)
        row = self.admin.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name=%s AND column_name=%s",
            (TABLE, "raw_bytes"),
        ).fetchone()
        self.assertEqual(row, ("bytea",))
        self.assertIn("ON CONFLICT (resource_key) DO NOTHING", 
                      __import__("v5.official_first_write_storage", fromlist=["INSERT_FIRST"]).INSERT_FIRST)

    def test_real_insert_and_same_transaction_bytea_readback(self):
        raw = b"original-\x00\xff-beforeinfo"
        p = plan_for(BEFORE1, raw, RACE1)
        result = persist_first_http_capture(self.writer, p)
        self.assertEqual(result["status"], "INSERTED_AND_READBACK_MATCH_SOURCE_UNVERIFIED")
        self.assertTrue(result["inserted_this_attempt"])
        self.assertFalse(result["forward_eligible"])
        self.assertIsNone(result["first_observed_at"])
        frozen = self.admin.execute(
            "SELECT raw_bytes, raw_sha256, source_url FROM "
            "v5_official_source_first_capture WHERE resource_key=%s",
            (p["resource_key"],),
        ).fetchone()
        self.assertEqual(frozen[0], raw)
        self.assertEqual(frozen[1], hashlib.sha256(raw).hexdigest())
        self.assertEqual(frozen[2], BEFORE1)

    def test_repeat_identical_does_not_overwrite_original(self):
        p = plan_for(BEFORE1, b"same original", RACE1)
        persist_first_http_capture(self.writer, p)
        before = self.admin.execute(
            "SELECT stored_at, raw_bytes, response_completed_at "
            "FROM v5_official_source_first_capture WHERE resource_key=%s",
            (p["resource_key"],),
        ).fetchone()
        result = persist_first_http_capture(self.writer, p)
        after = self.admin.execute(
            "SELECT stored_at, raw_bytes, response_completed_at "
            "FROM v5_official_source_first_capture WHERE resource_key=%s",
            (p["resource_key"],),
        ).fetchone()
        self.assertEqual(result["status"], "EXISTING_IDENTICAL_FIRST_CAPTURE")
        self.assertFalse(result["inserted_this_attempt"])
        self.assertEqual(before, after)
        self.assertEqual(self.count(), 1)

    def test_different_body_same_race_is_rolled_back(self):
        original = plan_for(BEFORE1, b"first captured", RACE1)
        persist_first_http_capture(self.writer, original)
        other = plan_for(BEFORE1, b"later changed page", RACE1)
        with self.assertRaisesRegex(
            FirstWriteRejected, "^FIRST_WRITE_COLLISION_OR_TAMPERING$"
        ):
            persist_first_http_capture(self.writer, other)
        self.assertEqual(self.count(), 1)
        self.assertEqual(
            self.admin.execute(
                "SELECT raw_bytes FROM v5_official_source_first_capture "
                "WHERE resource_key=%s", (original["resource_key"],)
            ).fetchone()[0], b"first captured"
        )

    def test_query_reorder_same_resource_rejected_without_overwrite(self):
        original = plan_for(BEFORE1, b"first capture", RACE1)
        persist_first_http_capture(self.writer, original)
        reordered = BASE + "beforeinfo?hd=20261010&jcd=09&rno=4"
        with self.assertRaisesRegex(
            FirstWriteRejected, "^FIRST_WRITE_COLLISION_OR_TAMPERING$"
        ):
            persist_first_http_capture(
                self.writer, plan_for(reordered, b"first capture", RACE1)
            )
        self.assertEqual(self.count(), 1)

    def test_two_separate_races_have_different_first_captures(self):
        persist_first_http_capture(
            self.writer, plan_for(BEFORE1, b"race-four", RACE1)
        )
        persist_first_http_capture(
            self.writer, plan_for(BEFORE2, b"race-five", RACE2)
        )
        self.assertEqual(self.count(), 2)

    def test_daily_K_bundle_is_not_attributed_to_one_race(self):
        p = plan_for(K_FILE, b"K-file-binary-synthetic", None)
        persist_first_http_capture(self.writer, p)
        self.assertEqual(p["resource_key"], "official_k_file:261009")
        self.assertIsNone(
            self.admin.execute(
                "SELECT race_id FROM v5_official_source_first_capture "
                "WHERE resource_key=%s", (p["resource_key"],)
            ).fetchone()[0]
        )

    def test_insert_select_role_cannot_update_or_delete(self):
        p = plan_for(BEFORE1, b"immutable-to-writer", RACE1)
        persist_first_http_capture(self.writer, p)
        with self.assertRaises(InsufficientPrivilege):
            self.writer.execute(
                "UPDATE v5_official_source_first_capture "
                "SET raw_bytes=%s WHERE resource_key=%s",
                (b"evil", p["resource_key"]),
            )
        with self.assertRaises(InsufficientPrivilege):
            self.writer.execute(
                "DELETE FROM v5_official_source_first_capture "
                "WHERE resource_key=%s", (p["resource_key"],)
            )
        self.assertEqual(self.count(), 1)
        self.assertFalse(
            self.admin.execute(
                "SELECT raw_bytes <> %s FROM v5_official_source_first_capture "
                "WHERE resource_key=%s",
                (b"immutable-to-writer", p["resource_key"]),
            ).fetchone()[0]
        )

    def test_privileged_tampering_is_detected_not_prevented(self):
        p = plan_for(BEFORE1, b"valid-first", RACE1)
        persist_first_http_capture(self.writer, p)
        # DB owner still has UPDATE rights: IMPORTANT deployment limitation.
        self.admin.execute(
            "UPDATE v5_official_source_first_capture "
            "SET raw_bytes=%s WHERE resource_key=%s",
            (b"tampered-owner", p["resource_key"]),
        )
        with self.assertRaisesRegex(
            FirstWriteRejected, "^FIRST_WRITE_COLLISION_OR_TAMPERING$"
        ):
            persist_first_http_capture(self.writer, p)
        self.assertEqual(self.count(), 1)


if __name__ == "__main__":
    unittest.main()
