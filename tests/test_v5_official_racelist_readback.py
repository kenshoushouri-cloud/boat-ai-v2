# -*- coding: utf-8 -*-
"""V5 source binder: synthetic original SQL readback; no real network/DB."""
from __future__ import annotations

import hashlib
import unittest
from copy import deepcopy
from datetime import datetime

from v5.official_first_write_storage import READ_FIRST
from v5.official_racelist_readback import (
    RacelistNotVerified, bind_first_write_racelist,
)

RACE = "20261010_09_04"
URL = "https://www.boatrace.jp/owpc/pc/race/racelist?rno=4&jcd=09&hd=20261010"
ROSTER_AT = "2026-10-10T11:46:00+09:00"
BEFORE_AT = "2026-10-10T11:50:00+09:00"
CUTOFF = "2026-10-10T11:55:00+09:00"


def make_html(*, missing=None, duplicate_lane=None, duplicate_racer=None,
              canceled=None, missing_reg=None, bad_header=False, extra=""):
    rows = []
    for lane in range(1, 7):
        if lane == missing:
            continue
        racer = 1000 + (duplicate_racer if lane == 6 and duplicate_racer else lane)
        registration = "" if lane == missing_reg else f"{racer} / A1"
        marker = "欠場" if lane == canceled else "出走"
        rows.append(
            f"<tr><td>{lane}</td><td>写真</td><td>{registration}</td>"
            f"<td>選手{lane}</td><td>{marker}</td></tr>"
        )
    if duplicate_lane is not None:
        rows.append(
            f"<tr><td>{duplicate_lane}</td><td>写真</td>"
            "<td>1999 / B1</td><td>重複</td></tr>"
        )
    heading = "不明テーブル" if bad_header else "写真 登録番号/級別"
    return (
        f"<html><body><table><thead><tr><th>{heading}</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>{extra}</body></html>"
    ).encode("utf-8")


def row_for(raw=None):
    raw = make_html() if raw is None else raw
    return {
        "resource_key": "official_racelist:" + RACE,
        "source_kind": "official_racelist",
        "race_id": RACE,
        "source_url": URL,
        "request_started_at": "2026-10-10T11:45:59+09:00",
        "response_completed_at": ROSTER_AT,
        "raw_bytes": memoryview(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
    }


class Cursor:
    def __init__(self, db):
        self.db = db
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, params):
        self.db.commands.append((sql, params))
        if self.db.fail:
            raise RuntimeError("synthetic secret hidden by binder")
    def fetchone(self):
        return self.db.row


class DB:
    def __init__(self, row=None, *, absent=False, fail=False):
        self.row = None if absent else row_for() if row is None else row
        self.fail = fail
        self.commands = []
    def cursor(self):
        return Cursor(self)


def run(db=None, **changes):
    db = DB() if db is None else db
    values = dict(
        connection=db, expected_race_id=RACE,
        beforeinfo_captured_at=BEFORE_AT,
        prediction_cutoff_at=CUTOFF,
    )
    values.update(changes)
    return bind_first_write_racelist(**values)


class TestV5RacelistReadback(unittest.TestCase):
    def denied(self, reason, db=None, **params):
        with self.assertRaises(RacelistNotVerified) as error:
            run(db=db, **params)
        self.assertEqual(str(error.exception), reason)

    def test_six_unique_racers_from_original_readback(self):
        db=DB()
        r=run(db)
        self.assertEqual(len(r["entries"]),6)
        self.assertEqual([x["racer_number"] for x in r["entries"]],
                         [1001,1002,1003,1004,1005,1006])
        self.assertTrue(r["readback_consistent"])
        self.assertFalse(r["all_active_verified"])
        self.assertFalse(r["first_write_confirmed"])
        self.assertFalse(r["forward_eligible"])
        self.assertEqual(db.commands,[(READ_FIRST,("official_racelist:"+RACE,))])

    def test_six_candidate_rows_not_self_attested_active(self):
        r=run()
        self.assertTrue(all(x["no_cancellation_marker"] for x in r["entries"]))
        self.assertTrue(all(x["active_verified"] is False for x in r["entries"]))

    def test_missing_first_write_row_denied(self):
        self.denied("RACELIST_FIRST_WRITE_NOT_FOUND",DB(absent=True))

    def test_unavailable_db_denied_before_read(self):
        self.denied("EXPLICIT_READ_CONNECTION_REQUIRED",connection=object())

    def test_bad_race_id_denied_before_db(self):
        db=DB()
        self.denied("INVALID_RACE_ID",db,expected_race_id="20261010_09_99")
        self.assertEqual(db.commands,[])

    def test_wrong_frozen_race_id_denied(self):
        row=row_for();row["race_id"]="20261010_09_05"
        self.denied("RACELIST_SOURCE_IDENTITY_MISMATCH",DB(row))

    def test_wrong_frozen_source_url_denied(self):
        row=row_for();row["source_url"]=URL.replace("rno=4","rno=5")
        self.denied("RACELIST_SOURCE_IDENTITY_MISMATCH",DB(row))

    def test_wrong_source_kind_denied(self):
        row=row_for();row["source_kind"]="official_beforeinfo"
        self.denied("RACELIST_SOURCE_IDENTITY_MISMATCH",DB(row))

    def test_mutable_or_tampered_bytes_rejected(self):
        row=row_for();row["raw_bytes"]=b"changed original"
        self.denied("RACELIST_ORIGINAL_SHA256_MISMATCH",DB(row))

    def test_forged_digest_rejected(self):
        row=row_for();row["raw_sha256"]="0"*64
        self.denied("RACELIST_ORIGINAL_SHA256_MISMATCH",DB(row))

    def test_missing_original_bytes_rejected(self):
        row=row_for();row["raw_bytes"]=None
        self.denied("RACELIST_ORIGINAL_BYTES_MISSING",DB(row))

    def test_5_boats_refused(self):
        self.denied("RACELIST_NOT_SIX_UNIQUE_LANES",DB(row_for(make_html(missing=5))))

    def test_duplicate_lane_refused(self):
        self.denied("RACELIST_NOT_SIX_UNIQUE_LANES",
                    DB(row_for(make_html(duplicate_lane=4))))

    def test_duplicate_racer_refused(self):
        self.denied("RACELIST_DUPLICATE_OR_MISSING_RACERS",
                    DB(row_for(make_html(duplicate_racer=1))))

    def test_explicit_cancelled_racer_refused(self):
        self.denied("RACELIST_CANCEL_MARKER_PRESENT",
                    DB(row_for(make_html(canceled=2))))

    def test_missing_registration_rejected(self):
        self.denied("RACELIST_REGISTRATION_UNVERIFIED",
                    DB(row_for(make_html(missing_reg=3))))

    def test_non_roster_table_text_does_not_count(self):
        self.denied("RACELIST_STRUCTURED_TABLE_MISSING_OR_AMBIGUOUS",
                    DB(row_for(make_html(bad_header=True))))

    def test_ambiguous_two_roster_tables_refused(self):
        raw=make_html()
        self.denied("RACELIST_STRUCTURED_TABLE_MISSING_OR_AMBIGUOUS",
                    DB(row_for(raw+raw)))

    def test_late_roster_response_denied(self):
        row=row_for();row["response_completed_at"]="2026-10-10T11:56:00+09:00"
        self.denied("RACELIST_OBSERVATION_AFTER_CUTOFF",DB(row))

    def test_roster_older_than_24h_rejected(self):
        row=row_for();row["response_completed_at"]="2026-10-09T11:45:00+09:00"
        row["request_started_at"]="2026-10-09T11:44:59+09:00"
        self.denied("RACELIST_CAPTURE_TIME_OUT_OF_BOUNDS",DB(row))

    def test_unzoned_cutoff_rejected(self):
        self.denied("UNVERIFIED_DECISION_CLOCK",
                    prediction_cutoff_at="2026-10-10T11:55:00")

    def test_db_exception_does_not_expose_secrets(self):
        self.denied("RACELIST_DB_READ_FAILED",DB(fail=True))

    def test_utc_readback_timestamp_equivalent(self):
        row=row_for()
        row["request_started_at"]=datetime.fromisoformat("2026-10-10T02:45:59+00:00")
        row["response_completed_at"]=datetime.fromisoformat("2026-10-10T02:46:00+00:00")
        result=run(DB(row))
        self.assertEqual(result["captured_at"],ROSTER_AT)

    def test_table_digest_does_not_prove_true_first_capture(self):
        r=run()
        self.assertEqual(r["contract"],"V5_RACELIST_ORIGINAL_READBACK_V1")
        self.assertIn("remain unproven",r["limitations"])
        self.assertFalse(r["all_active_verified"])


if __name__=="__main__":
    unittest.main()
