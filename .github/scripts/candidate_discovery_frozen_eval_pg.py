# -*- coding: utf-8 -*-
"""Evaluate an already-frozen Candidate Discovery feed (READ ONLY).

This script never regenerates candidates. It consumes the exact JSON artifact that
was produced before results evaluation, verifies its SHA-256 sidecar, then joins
only official result data needed to score the frozen tickets.

No DB writes, no LINE sends, no BUY action, no Production behavior changes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

INPUT = Path(os.getenv("CANDIDATE_FORWARD_INPUT", "candidate-discovery-main-feed.json"))
HASH_FILE = Path(os.getenv("CANDIDATE_FORWARD_HASH", str(INPUT) + ".sha256"))
OUTPUT = Path(os.getenv("CANDIDATE_FORWARD_EVAL_OUTPUT", "candidate-discovery-forward-eval.json"))
STAKE_PER_TICKET = 100


def norm_ticket(value: Any) -> str:
    nums = re.findall(r"[1-6]", str(value or ""))
    if len(nums) < 3 or len(set(nums[:3])) != 3:
        return ""
    return "-".join(nums[:3])


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_sha256(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").strip()
    token = raw.split()[0].strip().lower() if raw else ""
    if not re.fullmatch(r"[0-9a-f]{64}", token):
        raise RuntimeError("invalid SHA-256 sidecar")
    return token


def validate_frozen_feed(data: dict[str, Any]) -> list[dict[str, Any]]:
    if data.get("contract") != "candidate_discovery_main_feed_v1":
        raise RuntimeError("unexpected candidate feed contract")
    if data.get("mutation_performed") is not False:
        raise RuntimeError("candidate artifact reports mutation")
    if data.get("line_sent") is not False:
        raise RuntimeError("candidate artifact reports LINE send")
    if data.get("purchase_action") is not False:
        raise RuntimeError("candidate artifact reports purchase action")
    feed = data.get("feed")
    if not isinstance(feed, list) or not feed:
        raise RuntimeError("frozen feed is empty")
    summary = data.get("summary") or {}
    if int(summary.get("scheduled_races") or 0) <= 0:
        raise RuntimeError("frozen feed has no scheduled races")
    if int(summary.get("core_races") or 0) != 6:
        raise RuntimeError("frozen feed core-race contract mismatch")
    return feed


def load_results(conn: psycopg.Connection[Any], race_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not race_ids:
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """select race_id,trifecta_ticket,trifecta_payout_yen,result_status,race_status
                 from v2_results
                where race_id=any(%s)""",
            (race_ids,),
        )
        out = {}
        for row in cur.fetchall():
            item = dict(row)
            ticket = norm_ticket(item.get("trifecta_ticket"))
            payout = item.get("trifecta_payout_yen")
            if not ticket or payout is None:
                continue
            item["trifecta_ticket"] = ticket
            try:
                item["trifecta_payout_yen"] = int(payout)
            except Exception:
                continue
            out[str(item["race_id"])] = item
        return out


def evaluate(feed: list[dict[str, Any]], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_tier: dict[str, dict[str, int]] = defaultdict(lambda: {
        "races": 0, "tickets": 0, "hits": 0, "investment_yen": 0, "return_yen": 0
    })
    evaluated_races = 0
    total_tickets = 0
    hits = 0
    investment = 0
    returns = 0
    missing_results = 0
    rows = []

    for race in feed:
        race_id = str(race.get("race_id") or "")
        tier = str(race.get("tier") or "?")
        tickets = []
        for item in race.get("tickets") or []:
            ticket = norm_ticket((item or {}).get("ticket"))
            if ticket and ticket not in tickets:
                tickets.append(ticket)
        result = results.get(race_id)
        if result is None:
            missing_results += 1
            rows.append({"race_id": race_id, "tier": tier, "status": "RESULT_NOT_READY", "tickets": tickets})
            continue

        evaluated_races += 1
        n = len(tickets)
        inv = n * STAKE_PER_TICKET
        winning = str(result["trifecta_ticket"])
        hit = winning in tickets
        ret = int(result["trifecta_payout_yen"]) if hit else 0

        total_tickets += n
        investment += inv
        returns += ret
        hits += 1 if hit else 0
        bucket = by_tier[tier]
        bucket["races"] += 1
        bucket["tickets"] += n
        bucket["hits"] += 1 if hit else 0
        bucket["investment_yen"] += inv
        bucket["return_yen"] += ret
        rows.append({
            "race_id": race_id,
            "tier": tier,
            "status": "EVALUATED",
            "tickets": tickets,
            "result_ticket": winning,
            "payout_yen": int(result["trifecta_payout_yen"]),
            "hit": hit,
            "investment_yen": inv,
            "return_yen": ret,
        })

    tier_summary = {}
    for tier, bucket in sorted(by_tier.items()):
        inv = bucket["investment_yen"]
        tier_summary[tier] = {
            **bucket,
            "hit_rate_pct": round(bucket["hits"] / bucket["races"] * 100, 3) if bucket["races"] else None,
            "roi_pct": round(bucket["return_yen"] / inv * 100, 3) if inv else None,
        }

    return {
        "evaluated_races": evaluated_races,
        "missing_results": missing_results,
        "tickets": total_tickets,
        "hits": hits,
        "hit_rate_pct": round(hits / evaluated_races * 100, 3) if evaluated_races else None,
        "investment_yen": investment,
        "return_yen": returns,
        "profit_yen": returns - investment,
        "roi_pct": round(returns / investment * 100, 3) if investment else None,
        "by_tier": tier_summary,
        "rows": rows,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    if not INPUT.exists() or not HASH_FILE.exists():
        raise RuntimeError("frozen feed JSON and SHA-256 sidecar are required")

    expected = expected_sha256(HASH_FILE)
    actual = file_sha256(INPUT)
    if actual != expected:
        raise RuntimeError(f"frozen feed SHA-256 mismatch expected={expected} actual={actual}")

    data = json.loads(INPUT.read_text(encoding="utf-8"))
    feed = validate_frozen_feed(data)
    race_ids = [str(row.get("race_id") or "") for row in feed if row.get("race_id")]

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='5s'")
        results = load_results(conn, race_ids)
        conn.rollback()

    evaluated = evaluate(feed, results)
    out = {
        "contract": "candidate_discovery_frozen_forward_eval_v1",
        "source_contract": data.get("contract"),
        "source_date": (data.get("summary") or {}).get("date"),
        "source_sha256": actual,
        "stake_per_ticket_yen": STAKE_PER_TICKET,
        "summary": {k: v for k, v in evaluated.items() if k != "rows"},
        "rows": evaluated["rows"],
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    s = out["summary"]
    print(f"CANDIDATE_FORWARD_SOURCE_SHA256={actual}", flush=True)
    print(
        "CANDIDATE_FORWARD_SUMMARY="
        + json.dumps({k: s[k] for k in ("evaluated_races", "missing_results", "tickets", "hits", "investment_yen", "return_yen", "profit_yen", "roi_pct")}, sort_keys=True),
        flush=True,
    )
    print("CANDIDATE_FORWARD_DB_WRITE=0 LINE=0 PURCHASE_ACTION=false PROD_CHANGE=0", flush=True)
    print("CANDIDATE_FORWARD_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
