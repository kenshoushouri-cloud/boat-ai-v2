# -*- coding: utf-8 -*-
"""Settle exact immutable V4 prospective-freeze artifacts against official results.

Artifacts are validated and core tickets are frozen in memory before any result
query is executed. No candidate reconstruction, odds read, DB write, LINE,
purchase, or Production change is performed.
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

UNIT_YEN = 100
ARTIFACT_DIR = Path(os.getenv("V4_FORMAL_ARTIFACT_DIR", "v4-artifacts"))
OUTPUT = Path(os.getenv("V4_FORMAL_SETTLEMENT_OUTPUT", "v4-formal-artifact-settlement.json"))

EXPECTED = {
    "2026-09-21": {
        "run_id": 35549611949,
        "artifact_id": 10617384166,
        "archive_sha256": "b40c34f99c42685ebbee330c90eeab0f45a829cfc18513d2517d9fc9da9da666",
        "core_sha256": "d07ec4347ccd30eb82c8511da9118784a124cbe90459fe8d2ce5f4c2773debaf",
    },
    "2026-09-22": {
        "run_id": 35667553345,
        "artifact_id": 10670080150,
        "archive_sha256": "60ae93e3758679fc0109fd180bbd66a54978c0b483514a724bb5ace376c5a94c",
        "core_sha256": "1514b991505565763f412bdc3515eb64613c4de61d49cd51748fb01af61373d9",
    },
    "2026-09-23": {
        "run_id": 35797576979,
        "artifact_id": 10724298102,
        "archive_sha256": "9b7bb37e8d91753923774acb728499b499a3b12f2919c91ff321a7369d1c7a32",
        "core_sha256": "8a50f645239778a3adae8fb24f8c5df18b6c25d698a1136f00006482c8075639",
    },
    "2026-09-24": {
        "run_id": 35933702258,
        "artifact_id": 10782581362,
        "archive_sha256": "4527b05e320dfcf546d2d9604edbbc5721cc50b4de2da723935eec5e7b5a0997",
        "core_sha256": "20c4810930960770ea082cbbfe16c264ef3bcdd40b41acb1100711f2c06cb1a3",
    },
    "2026-09-25": {
        "run_id": 36072738431,
        "artifact_id": 10838744179,
        "archive_sha256": "6abac7b17061dd8e6449c98ec7cba21f2b2ae708804890076c7304e7f52bcca1",
        "core_sha256": "c59cca328a34a1a05dca532368447a8c7eac366da70f37fefbb8cf85f1abfb67",
    },
    "2026-09-26": {
        "run_id": 36201131582,
        "artifact_id": 10891628808,
        "archive_sha256": "59812eb598a48965621f4b9b4842c65312c4c7914200754627dc71f2d8f120af",
        "core_sha256": "1b3596d1aed21d9b1c8125703bab86a076c4a9ebafee3c515a47c2f480a7da3c",
    },
    "2026-09-27": {
        "run_id": 36279479671,
        "artifact_id": 10918742073,
        "archive_sha256": "d251c0d918964e3dc8c467b8f43038cae0571892a2b0539ad8ccf27a39d98da0",
        "core_sha256": "8907e2443a172d7938395145824497479f3f3bf23d3170943973545adc47f8d3",
    },
}


def norm_ticket(value: Any) -> str:
    xs = re.findall(r"[1-6]", str(value or ""))
    return "-".join(xs[:3]) if len(xs) >= 3 else ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_and_freeze() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    frozen: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for day, exp in sorted(EXPECTED.items()):
        path = ARTIFACT_DIR / f"{day}.zip"
        if not path.exists():
            raise RuntimeError(f"artifact missing: {path}")
        got_archive = sha256_file(path)
        if got_archive != exp["archive_sha256"]:
            raise RuntimeError(f"archive sha mismatch {day}: {got_archive}")

        with zipfile.ZipFile(path) as zf:
            payload = json.loads(zf.read("candidate-discovery-v4-prospective-freeze.json"))
            core_hash_text = zf.read("candidate-discovery-v4-prospective-freeze.json.core.sha256").decode("utf-8").strip()
        got_core = core_hash_text.split()[0]
        if got_core != exp["core_sha256"]:
            raise RuntimeError(f"core sha mismatch {day}: {got_core}")

        fp = payload.get("freeze_provenance") or {}
        summary = payload.get("summary") or {}
        if str(summary.get("date")) != day or str(fp.get("target_date")) != day:
            raise RuntimeError(f"target date mismatch: {day}")
        if payload.get("prospective_evidence_eligible") is not True:
            raise RuntimeError(f"evidence not eligible: {day}")
        if fp.get("prospective_evidence_eligible") is not True:
            raise RuntimeError(f"freeze evidence not eligible: {day}")
        if fp.get("outcome_read") is not False or fp.get("payout_read") is not False:
            raise RuntimeError(f"pre-result read contract violated: {day}")
        if payload.get("purchase_action") is not False:
            raise RuntimeError(f"purchase_action not false: {day}")
        if payload.get("mutation_performed") is not False or payload.get("line_sent") is not False:
            raise RuntimeError(f"mutation/line contract violated: {day}")
        if int(summary.get("core_races") or 0) != 6 or int(summary.get("core_tickets") or 0) != 12:
            raise RuntimeError(f"core completeness mismatch: {day}")

        core_rows = sorted(
            [r for r in payload.get("feed", []) if r.get("daily_rank") is not None],
            key=lambda r: int(r["daily_rank"]),
        )
        if [int(r["daily_rank"]) for r in core_rows] != [1, 2, 3, 4, 5, 6]:
            raise RuntimeError(f"daily rank mismatch: {day}")

        for row in core_rows:
            tickets = sorted(
                [t for t in row.get("tickets", []) if t.get("core_order") in (1, 2)],
                key=lambda t: int(t["core_order"]),
            )
            if [int(t["core_order"]) for t in tickets] != [1, 2]:
                raise RuntimeError(f"ticket order mismatch: {row.get('race_id')}")
            frozen.append({
                "date": day,
                "race_id": str(row["race_id"]),
                "daily_rank": int(row["daily_rank"]),
                "head_lane": int(row["head_lane"]),
                "ticket1": norm_ticket(tickets[0]["ticket"]),
                "ticket2": norm_ticket(tickets[1]["ticket"]),
            })
        provenance.append({
            "date": day,
            "run_id": exp["run_id"],
            "artifact_id": exp["artifact_id"],
            "archive_sha256": got_archive,
            "core_sha256": got_core,
            "generated_at_jst": payload.get("generated_at_jst"),
            "earliest_core_deadline_at_jst": fp.get("earliest_core_deadline_at_jst"),
            "earliest_feed_deadline_at_jst": fp.get("earliest_feed_deadline_at_jst"),
        })

    if len(frozen) != 42 or len({r["race_id"] for r in frozen}) != 42:
        raise RuntimeError("expected exact 42 unique frozen core races")
    return frozen, provenance


def summarize(rows: list[dict[str, Any]], points: int) -> dict[str, Any]:
    settled = [r for r in rows if r["official"]]
    investment = len(settled) * UNIT_YEN * points
    gross = 0
    exact_hits = 0
    for r in settled:
        picks = [r["ticket1"]] if points == 1 else [r["ticket1"], r["ticket2"]]
        if r["actual_ticket"] in picks:
            exact_hits += 1
            gross += int(r["payout_yen"])
    return {
        "settled_races": len(settled),
        "bets": len(settled) * points,
        "hits": exact_hits,
        "investment_yen": investment,
        "return_yen": gross,
        "profit_yen": gross - investment,
        "roi_pct": round(gross / investment * 100.0, 4) if investment else None,
    }


def main() -> None:
    print("V4_FORMAL_SETTLEMENT_POLICY=EXACT_IMMUTABLE_ARTIFACTS_BEFORE_RESULT_QUERY", flush=True)
    print("V4_FORMAL_SETTLEMENT_RECONSTRUCT_CANDIDATES=0 ODDS_READ=0", flush=True)
    print("V4_FORMAL_SETTLEMENT_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    # Critical ordering: validate/freeze every artifact before DB result access.
    frozen, provenance = load_and_freeze()
    print(f"V4_FORMAL_SETTLEMENT_FROZEN_RACES={len(frozen)}", flush=True)

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    ids = [r["race_id"] for r in frozen]

    results: dict[str, dict[str, Any]] = {}
    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute(
                """
                select race_id,result_status,race_status,first_lane,
                       trifecta_ticket,trifecta_payout_yen
                  from v2_results
                 where race_id=any(%s)
                """,
                (ids,),
            )
            results = {str(r["race_id"]): dict(r) for r in cur.fetchall()}
        conn.rollback()

    settled_rows: list[dict[str, Any]] = []
    for row in frozen:
        res = results.get(row["race_id"]) or {}
        official = (
            str(res.get("result_status") or "").lower() == "official"
            and str(res.get("race_status") or "").lower() == "official"
            and norm_ticket(res.get("trifecta_ticket")) != ""
            and int(res.get("trifecta_payout_yen") or 0) > 0
        )
        settled_rows.append({
            **row,
            "result_present": bool(res),
            "result_status": str(res.get("result_status") or ""),
            "race_status": str(res.get("race_status") or ""),
            "official": official,
            "actual_ticket": norm_ticket(res.get("trifecta_ticket")) if official else None,
            "payout_yen": int(res.get("trifecta_payout_yen") or 0) if official else 0,
            "actual_head_lane": int(res.get("first_lane") or 0) if official else None,
        })

    by_day = []
    for day in sorted(EXPECTED):
        rr = [r for r in settled_rows if r["date"] == day]
        complete = len(rr) == 6 and all(r["official"] for r in rr)
        top1 = summarize(rr, 1)
        top2 = summarize(rr, 2)
        head_n = sum(int(r["official"]) for r in rr)
        head_hits = sum(int(r["official"] and r["head_lane"] == r["actual_head_lane"]) for r in rr)
        by_day.append({
            "date": day,
            "complete": complete,
            "official_races": head_n,
            "head_hits": head_hits,
            "head_accuracy_pct": round(head_hits / head_n * 100.0, 4) if head_n else None,
            "top1": top1,
            "top2": top2,
        })

    complete_dates = {x["date"] for x in by_day if x["complete"]}
    complete_rows = [r for r in settled_rows if r["date"] in complete_dates]
    overall_top1 = summarize(complete_rows, 1)
    overall_top2 = summarize(complete_rows, 2)
    head_n = len(complete_rows)
    head_hits = sum(int(r["head_lane"] == r["actual_head_lane"]) for r in complete_rows)

    out = {
        "contract": "v4_formal_immutable_artifact_settlement_v1",
        "artifact_provenance": provenance,
        "frozen_core_races": frozen,
        "days": by_day,
        "complete_day_count": len(complete_dates),
        "complete_day_dates": sorted(complete_dates),
        "complete_day_only": {
            "head": {
                "races": head_n,
                "hits": head_hits,
                "accuracy_pct": round(head_hits / head_n * 100.0, 4) if head_n else None,
            },
            "top1": overall_top1,
            "top2": overall_top2,
            "profitable_days_top1": sum(int(x["complete"] and x["top1"]["profit_yen"] > 0) for x in by_day),
            "profitable_days_top2": sum(int(x["complete"] and x["top2"]["profit_yen"] > 0) for x in by_day),
        },
        "pending_or_invalid_races": [
            {
                "date": r["date"],
                "race_id": r["race_id"],
                "result_present": r["result_present"],
                "result_status": r["result_status"],
                "race_status": r["race_status"],
            }
            for r in settled_rows if not r["official"]
        ],
        "safety": {
            "artifact_first": True,
            "candidate_reconstruction": False,
            "odds_read": False,
            "db_write": False,
            "line": False,
            "buy": False,
            "production_change": False,
            "promotion_allowed": False,
        },
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print("V4_FORMAL_SETTLEMENT_DAYS=" + json.dumps(by_day, sort_keys=True), flush=True)
    print("V4_FORMAL_SETTLEMENT_COMPLETE=" + json.dumps(out["complete_day_only"], sort_keys=True), flush=True)
    print("V4_FORMAL_SETTLEMENT_PENDING=" + json.dumps(out["pending_or_invalid_races"], sort_keys=True), flush=True)
    print("V4_FORMAL_SETTLEMENT_PROMOTION_ALLOWED=0", flush=True)
    print("V4_FORMAL_SETTLEMENT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
