# -*- coding: utf-8 -*-
"""Read-only common-economics audit for exact formal V4 TOP2 artifacts.

All six immutable formal artifacts are validated and frozen before any result
query. No candidate regeneration or odds read is performed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research.forward_economics import (
    forward_report,
    normalize_formal_settlement_rows,
)

ARTIFACT_DIR = Path(os.getenv("V4_COMMON_ARTIFACT_DIR", "v4-common-artifacts"))
EXPECTED = {
    "2026-09-21": {
        "archive": "b40c34f99c42685ebbee330c90eeab0f45a829cfc18513d2517d9fc9da9da666",
        "core": "d07ec4347ccd30eb82c8511da9118784a124cbe90459fe8d2ce5f4c2773debaf",
    },
    "2026-09-22": {
        "archive": "60ae93e3758679fc0109fd180bbd66a54978c0b483514a724bb5ace376c5a94c",
        "core": "1514b991505565763f412bdc3515eb64613c4de61d49cd51748fb01af61373d9",
    },
    "2026-09-23": {
        "archive": "9b7bb37e8d91753923774acb728499b499a3b12f2919c91ff321a7369d1c7a32",
        "core": "8a50f645239778a3adae8fb24f8c5df18b6c25d698a1136f00006482c8075639",
    },
    "2026-09-24": {
        "archive": "4527b05e320dfcf546d2d9604edbbc5721cc50b4de2da723935eec5e7b5a0997",
        "core": "20c4810930960770ea082cbbfe16c264ef3bcdd40b41acb1100711f2c06cb1a3",
    },
    "2026-09-25": {
        "archive": "6abac7b17061dd8e6449c98ec7cba21f2b2ae708804890076c7304e7f52bcca1",
        "core": "c59cca328a34a1a05dca532368447a8c7eac366da70f37fefbb8cf85f1abfb67",
    },
    "2026-09-26": {
        "archive": "59812eb598a48965621f4b9b4842c65312c4c7914200754627dc71f2d8f120af",
        "core": "1b3596d1aed21d9b1c8125703bab86a076c4a9ebafee3c515a47c2f480a7da3c",
    },
}
EXPECTED_TOP2 = {
    "evaluated": 32,
    "hits": 10,
    "investment_yen": 6400,
    "return_yen": 10970,
    "profit_yen": 4570,
    "roi_pct": 171.4062,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ticket(value: Any) -> str:
    xs = re.findall(r"[1-6]", str(value or ""))
    return "-".join(xs[:3]) if len(xs) >= 3 else ""


def freeze_artifacts() -> list[dict[str, Any]]:
    frozen = []
    for day, exp in sorted(EXPECTED.items()):
        path = ARTIFACT_DIR / f"{day}.zip"
        got = sha256_file(path)
        if got != exp["archive"]:
            raise RuntimeError(f"archive SHA mismatch {day}: {got}")
        with zipfile.ZipFile(path) as zf:
            formal = json.loads(zf.read("candidate-discovery-v4-prospective-freeze.json"))
            core_text = zf.read(
                "candidate-discovery-v4-prospective-freeze.json.core.sha256"
            ).decode("utf-8").strip()
        core_sha = core_text.split()[0]
        if core_sha != exp["core"]:
            raise RuntimeError(f"core SHA mismatch {day}: {core_sha}")
        fp = formal.get("freeze_provenance") or {}
        summary = formal.get("summary") or {}
        if formal.get("prospective_evidence_eligible") is not True:
            raise RuntimeError(f"ineligible formal artifact: {day}")
        if fp.get("outcome_read") is not False or fp.get("payout_read") is not False:
            raise RuntimeError(f"formal artifact read outcome/payout: {day}")
        if formal.get("purchase_action") is not False:
            raise RuntimeError(f"purchase_action not false: {day}")
        if int(summary.get("core_races") or 0) != 6:
            raise RuntimeError(f"core race count mismatch: {day}")
        if int(summary.get("core_tickets") or 0) != 12:
            raise RuntimeError(f"core ticket count mismatch: {day}")

        rows = sorted(
            [r for r in formal.get("feed", []) if r.get("daily_rank") is not None],
            key=lambda r: int(r["daily_rank"]),
        )
        if [int(r["daily_rank"]) for r in rows] != [1, 2, 3, 4, 5, 6]:
            raise RuntimeError(f"rank mismatch: {day}")
        for row in rows:
            tickets = sorted(
                [t for t in row.get("tickets", []) if t.get("core_order") in (1, 2)],
                key=lambda t: int(t["core_order"]),
            )
            if len(tickets) != 2:
                raise RuntimeError(f"exact TOP2 tickets required: {row.get('race_id')}")
            frozen.append({
                "date": day,
                "race_date": day,
                "race_id": str(row["race_id"]),
                "daily_rank": int(row["daily_rank"]),
                "ticket1": ticket(tickets[0]["ticket"]),
                "ticket2": ticket(tickets[1]["ticket"]),
            })
    if len(frozen) != 36:
        raise RuntimeError("expected exact 36 frozen races")
    return frozen


def main() -> None:
    print("V4_COMMON_ECON_POLICY=ARTIFACT_FIRST_TOP2_COMMON_SEMANTICS", flush=True)
    print("V4_COMMON_ECON_RECONSTRUCT=0 ODDS_READ=0", flush=True)
    print("V4_COMMON_ECON_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    frozen = freeze_artifacts()
    print(f"V4_COMMON_ECON_FROZEN_RACES={len(frozen)}", flush=True)

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    ids = [r["race_id"] for r in frozen]

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute(
                """
                select race_id,result_status,race_status,
                       trifecta_ticket,trifecta_payout_yen
                  from v2_results
                 where race_id=any(%s)
                """,
                (ids,),
            )
            results = {str(r["race_id"]): dict(r) for r in cur.fetchall()}
        conn.rollback()

    if set(results) != set(ids):
        missing = sorted(set(ids) - set(results))
        raise RuntimeError(f"all six resolved formal days must have result rows: {missing}")

    raw_rows = []
    for row in frozen:
        res = results[row["race_id"]]
        actual = ticket(res.get("trifecta_ticket"))
        payout = int(res.get("trifecta_payout_yen") or 0)
        official = (
            str(res.get("result_status") or "").lower() == "official"
            and str(res.get("race_status") or "").lower() == "official"
            and bool(actual)
            and payout > 0
        )
        top2_hit = official and actual in {row["ticket1"], row["ticket2"]}
        raw_rows.append({
            **row,
            "official": official,
            "hit": top2_hit,
            "return_yen": payout if top2_hit else 0,
            "payout_yen": payout if top2_hit else 0,
        })

    normalized = normalize_formal_settlement_rows(
        raw_rows,
        investment_yen_per_bet=100,
        ticket_count=2,
    )
    report = forward_report(
        normalized,
        unit_yen=100,
        bootstrap_samples=20_000,
        bootstrap_seed=20260927,
    )

    overall = report["overall"]
    for key, expected in EXPECTED_TOP2.items():
        if overall[key] != expected:
            raise RuntimeError(
                f"V4 common economics parity failed {key}: {overall[key]} != {expected}"
            )

    print("V4_COMMON_ECON_COVERAGE=" + json.dumps(report["coverage"], sort_keys=True), flush=True)
    print("V4_COMMON_ECON_OVERALL=" + json.dumps(overall, sort_keys=True), flush=True)
    print("V4_COMMON_ECON_RISK=" + json.dumps(report["risk"], sort_keys=True), flush=True)
    print("V4_COMMON_ECON_HALVES=" + json.dumps(report["chronological_halves"], sort_keys=True), flush=True)
    print("V4_COMMON_ECON_BOOTSTRAP=" + json.dumps(report["day_bootstrap"], sort_keys=True), flush=True)
    print("V4_COMMON_ECON_RESULT=PASS_EXACT_V4_TOP2", flush=True)


if __name__ == "__main__":
    main()
