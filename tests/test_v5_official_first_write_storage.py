# -*- coding: utf-8 -*-
"""V5 mainline first-write plan and readback: synthetic, zero DB/network."""
from __future__ import annotations
import hashlib
import unittest
from copy import deepcopy
from datetime import datetime

from v5.official_http_receipt import prepare_official_http_receipt, UnverifiedCapture
from v5.official_first_write_storage import (
    DDL, INSERT_FIRST, READ_FIRST, prepare_first_write_storage,
    verify_first_write_readback,
)

BASE = "https://www.boatrace.jp/owpc/pc/race/"
QUERIES = "rno=4&jcd=09&hd=20261010"
K = "https://www1.mbrace.or.jp/od2/K/202610/k261009.lzh"
START = "2026-10-10T11:49:59+09:00"
END = "2026-10-10T11:50:00+09:00"
RACE = "20261010_09_04"
BODY = b"original \x00\xfe first HTTP response"


def source(kind="beforeinfo", *, body=BODY):
    url = K if kind == "k" else BASE + kind + "?" + QUERIES
    k = "official_k_file" if kind == "k" else "official_" + kind
    return prepare_official_http_receipt(
        requested_url=url, final_url=url, expected_source=k,
        http_status=200, response_body=body,
        request_started_at=START, response_completed_at=END,
    )


def prepared(kind="beforeinfo", **kw):
    return prepare_first_write_storage(
        source(kind), expected_race_id=None if kind == "k" else RACE, **kw,
    )


def stored(plan):
    key, kind, race, url, begun, completed, raw, sha = plan["params"]
    return dict(resource_key=key,source_kind=kind,race_id=race,
                source_url=url,request_started_at=begun,
                response_completed_at=completed,raw_bytes=memoryview(raw),
                raw_sha256=sha,stored_at=completed)


class TestV5FirstWriteStorage(unittest.TestCase):
    def denied(self, reason, proposal=None, expected=RACE):
        with self.assertRaises(UnverifiedCapture) as exc:
            prepare_first_write_storage(source() if proposal is None else proposal,
                                        expected_race_id=expected)
        self.assertEqual(str(exc.exception), reason)

    def test_valid_original_response_plan_is_never_a_write(self):
        p=prepared()
        self.assertEqual(p["status"],"PREPARED_ONLY_NO_DB_WRITE")
        self.assertEqual(p["resource_key"],"official_beforeinfo:"+RACE)
        self.assertIsNone(p["first_observed_at"])
        self.assertFalse(p["forward_eligible"])
        self.assertEqual(p["params"][6],BODY)
        self.assertIn("ON CONFLICT (resource_key) DO NOTHING", p["sql"])

    def test_resource_key_separates_racelist_and_beforeinfo_same_race(self):
        p=prepared("racelist")
        self.assertEqual(p["resource_key"],"official_racelist:"+RACE)
        self.assertEqual(p["race_id"],RACE)
        self.assertNotEqual(p["resource_key"],prepared()["resource_key"])

    def test_k_is_daily_file_not_individual_race(self):
        p=prepared("k")
        self.assertEqual(p["resource_key"],"official_k_file:261009")
        self.assertIsNone(p["race_id"])

    def test_daily_k_must_not_be_mislabeled_single_race(self):
        self.denied("RACE_ID_OR_DAILY_K_MISMATCH",source("k"))

    def test_wrong_race_id_rejected(self):
        self.denied("RACE_ID_OR_DAILY_K_MISMATCH",expected="20261010_09_05")

    def test_sql_is_append_only_and_isolated(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS v5_official_source_first_capture",DDL)
        self.assertIn("raw_bytes bytea",DDL)
        self.assertIn("source_kind, source_url",DDL)
        self.assertIn("ON CONFLICT (resource_key) DO NOTHING",INSERT_FIRST)
        self.assertNotIn("UPDATE ",INSERT_FIRST.upper())
        self.assertIn("WHERE resource_key=%s",READ_FIRST)

    def test_reject_fabricated_first_observed_time(self):
        s=source();s["first_observed_at"]=END
        self.denied("PREMATURE_FIRST_OBSERVATION_CLAIM",s)

    def test_reject_fake_readback_and_receipt_id(self):
        s=source();s["readback_confirmed"]=True
        self.denied("PREMATURE_FIRST_OBSERVATION_CLAIM",s)
        s=source();s["receipt_ref"]="already-first"
        self.denied("PREMATURE_FIRST_OBSERVATION_CLAIM",s)

    def test_reject_wrong_capture_contract(self):
        s=source();s["contract"]="historical"
        self.denied("HTTP_PROPOSAL_CONTRACT_REQUIRED",s)

    def test_reject_wrong_source_identity(self):
        s=source();s["source"]="official_k_file"
        self.denied("SOURCE_IDENTITY_CONFLICT",s)

    def test_missing_raw_and_bad_encoding(self):
        s=source();s["raw_base64"]=""
        self.denied("RAW_RESPONSE_MISSING",s)
        s=source();s["raw_base64"]="@@@"
        self.denied("RAW_RESPONSE_INVALID_ENCODING",s)

    def test_changed_raw_digest_rejected(self):
        s=source();s["raw_sha256"]="0"*64
        self.denied("RAW_RESPONSE_DIGEST_CONFLICT",s)
        s=source();s["raw_size_bytes"]=999
        self.denied("RAW_RESPONSE_DIGEST_CONFLICT",s)

    def test_changed_clock_claim_rejected(self):
        s=source();s["observed_at"]="2026-10-10T11:50:02+09:00"
        self.denied("OBSERVATION_CLOCK_CONFLICT",s)
        s=source();s["request_started_at"]="2026-10-10T11:51:00+09:00"
        self.denied("RESPONSE_CLOCK_CONFLICT",s)

    def test_matching_insert_readback_still_not_forward(self):
        p=prepared()
        r=verify_first_write_readback(p,stored(p),inserted_this_attempt=True)
        self.assertTrue(r["storage_consistent"])
        self.assertEqual(r["status"],"INSERTED_AND_READBACK_MATCH_SOURCE_UNVERIFIED")
        self.assertIsNone(r["first_observed_at"])
        self.assertFalse(r["first_write_confirmed"])
        self.assertFalse(r["forward_eligible"])

    def test_matching_repeated_fetch_is_idempotent_first_write(self):
        p=prepared()
        r=verify_first_write_readback(p,stored(p),inserted_this_attempt=False)
        self.assertTrue(r["storage_consistent"])
        self.assertEqual(r["status"],"EXISTING_IDENTICAL_FIRST_CAPTURE")
        self.assertFalse(r["forward_eligible"])

    def test_changed_body_at_same_race_is_collision(self):
        p=prepared()
        other=prepare_first_write_storage(
            source(body=b"later changed official page"),expected_race_id=RACE)
        self.assertEqual(other["resource_key"],p["resource_key"])
        r=verify_first_write_readback(other,stored(p),inserted_this_attempt=False)
        self.assertEqual(r["status"],"FIRST_WRITE_COLLISION_OR_TAMPERING")
        self.assertFalse(r["storage_consistent"])

    def test_different_race_at_same_storage_slot_is_collision(self):
        p=prepared()
        x=stored(p);x["race_id"]="20261010_09_05"
        r=verify_first_write_readback(p,x,inserted_this_attempt=False)
        self.assertEqual(r["status"],"FIRST_WRITE_COLLISION_OR_TAMPERING")

    def test_tampered_stored_source_url_or_time_is_rejected(self):
        p=prepared()
        for col,value in [
            ("source_url","https://bad.invalid"),
            ("source_kind","official_k_file"),
            ("response_completed_at","2026-10-10T12:01:00+09:00"),
        ]:
            x=stored(p);x[col]=value
            self.assertEqual(verify_first_write_readback(p,x,inserted_this_attempt=False)["status"],
                             "FIRST_WRITE_COLLISION_OR_TAMPERING")

    def test_corrupt_stored_binary_detected_even_if_claimed_digest_same(self):
        p=prepared();x=stored(p);x["raw_bytes"]=b"spoofed"
        r=verify_first_write_readback(p,x,inserted_this_attempt=True)
        self.assertEqual(r["status"],"FIRST_WRITE_COLLISION_OR_TAMPERING")

    def test_no_row_and_unknown_write_outcome_fail_closed(self):
        p=prepared()
        self.assertEqual(verify_first_write_readback(p,None,inserted_this_attempt=True)["status"],
                         "FIRST_WRITE_READBACK_MISSING")
        self.assertEqual(verify_first_write_readback(p,stored(p),inserted_this_attempt=None)["status"],
                         "INSERT_OUTCOME_UNVERIFIED")


if __name__=="__main__":
    unittest.main()
