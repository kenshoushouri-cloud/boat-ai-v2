# -*- coding: utf-8 -*-
"""Read-only prospective market annotation for an immutable V4 freeze.

This runner never regenerates candidates. It requires a pre-result Candidate
Discovery V4 freeze JSON plus its expected SHA-256 and provenance identifiers,
extracts only the immutable V4 core TOP1 tickets, and attaches timing-safe
MKT_LATE07_TOP2_SUPPORT_V1 tags from already-stored market snapshots.

No outcome table, message send, purchase action, persistence, or Production
configuration is touched. The database transaction is explicitly read-only.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from candidate_discovery_market_annotation_contract import (
    EXPECTED_TRIFECTA_TICKETS,
    LATE_MIN_HI,
    LATE_MIN_LO,
    MAX_SPREAD_SECONDS,
    PROSPECTIVE_START,
    V4_FEED_CONTRACT,
    annotate_feed,
    extract_core_top1,
)

FREEZE_PATH = Path(os.getenv("CANDIDATE_V4_FREEZE_JSON", "candidate-discovery-v4-main-feed.json"))
EXPECTED_SHA256 = (os.getenv("CANDIDATE_V4_FREEZE_SHA256") or "").strip().lower()
FREEZE_RUN_ID = (os.getenv("CANDIDATE_V4_FREEZE_RUN_ID") or "").strip()
FREEZE_ARTIFACT_ID = (os.getenv("CANDIDATE_V4_FREEZE_ARTIFACT_ID") or "").strip()
OUTPUT = Path(os.getenv("CANDIDATE_V4_MARKET_FORWARD_OUTPUT", "candidate-discovery-market-forward-annotation.json"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_verified_freeze() -> tuple[dict[str, Any], str]:
    if not FREEZE_PATH.is_file():
        raise RuntimeError(f"freeze JSON not found: {FREEZE_PATH}")
    if len(EXPECTED_SHA256) != 64 or any(c not in "0123456789abcdef" for c in EXPECTED_SHA256):
        raise RuntimeError("CANDIDATE_V4_FREEZE_SHA256 must be a 64-char lowercase SHA-256")
    if not FREEZE_RUN_ID or not FREEZE_ARTIFACT_ID:
        raise RuntimeError("freeze run/artifact provenance is required")

    actual = _sha256(FREEZE_PATH)
    if actual != EXPECTED_SHA256:
        raise RuntimeError(f"freeze SHA-256 mismatch: expected={EXPECTED_SHA256} actual={actual}")
    data = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("freeze document must be a JSON object")
    if data.get("contract") != V4_FEED_CONTRACT:
        raise RuntimeError(
            f"unexpected source contract: expected={V4_FEED_CONTRACT} actual={data.get('contract')}"
        )

    core = extract_core_top1(data, expected_core_races=6)
    if any(str(row["race_date"]) < PROSPECTIVE_START for row in core):
        raise RuntimeError(
            f"prospective annotator refuses pre-{PROSPECTIVE_START} freezes; "
            "use the dedicated historical wiring dry run instead"
        )
    return data, actual


def _fetch_valid_labels(
    conn: psycopg.Connection[Any], race_ids: list[str]
) -> dict[str, dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            with grouped as (
              select r.race_id,r.deadline_at,o.snapshot_label,
                     count(*)::bigint row_count,
                     count(distinct o.ticket)::bigint ticket_count,
                     count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint positive_odds_count,
                     min(o.snapshot_at) first_snapshot_at,
                     max(o.snapshot_at) last_snapshot_at
                from v2_races r
                join v2_realtime_odds_snapshots o on o.race_id=r.race_id
               where r.race_id=any(%s)
                 and r.deadline_at is not null
                 and o.snapshot_label is not null
               group by r.race_id,r.deadline_at,o.snapshot_label
            ), valid as (
              select *,
                     extract(epoch from (last_snapshot_at-first_snapshot_at)) spread_seconds,
                     extract(epoch from (deadline_at-last_snapshot_at))/60.0 lead_minutes
                from grouped
               where row_count=%s
                 and ticket_count=%s
                 and positive_odds_count=%s
                 and last_snapshot_at <= deadline_at
                 and extract(epoch from (last_snapshot_at-first_snapshot_at)) <= %s
            ), late as (
              select * from valid
               where lead_minutes >= %s and lead_minutes <= %s
            )
            select distinct on (race_id)
                   race_id,snapshot_label,last_snapshot_at,lead_minutes,spread_seconds
              from late
             order by race_id,last_snapshot_at desc,snapshot_label
            """,
            (
                race_ids,
                EXPECTED_TRIFECTA_TICKETS,
                EXPECTED_TRIFECTA_TICKETS,
                EXPECTED_TRIFECTA_TICKETS,
                MAX_SPREAD_SECONDS,
                LATE_MIN_LO,
                LATE_MIN_HI,
            ),
        )
        return {str(row["race_id"]): dict(row) for row in cur.fetchall()}


def _fetch_snapshot_odds(
    conn: psycopg.Connection[Any], labels: dict[str, dict[str, Any]]
) -> dict[str, dict[str, float]]:
    if not labels:
        return {}
    race_ids = list(labels)
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,snapshot_label,ticket,odds
              from v2_realtime_odds_snapshots
             where race_id=any(%s)
               and odds is not null and odds>1.0
             order by race_id,snapshot_label,ticket
            """,
            (race_ids,),
        )
        out: dict[str, dict[str, float]] = {rid: {} for rid in race_ids}
        for row in cur.fetchall():
            rid = str(row["race_id"])
            if str(row.get("snapshot_label") or "") != str(labels[rid]["snapshot_label"]):
                continue
            ticket = str(row.get("ticket") or "").replace("=", "-").replace(" ", "")
            odd = float(row["odds"])
            if ticket and math.isfinite(odd) and odd > 1.0:
                out[rid][ticket] = odd
        return out


def _market_input(
    labels: dict[str, dict[str, Any]], odds_by_race: dict[str, dict[str, float]]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for rid, label in labels.items():
        odds = odds_by_race.get(rid, {})
        if len(odds) != EXPECTED_TRIFECTA_TICKETS:
            continue
        result[rid] = {
            "lead_minutes": float(label["lead_minutes"]),
            "spread_seconds": float(label["spread_seconds"]),
            "snapshot_label": str(label["snapshot_label"]),
            "snapshot_at": str(label["last_snapshot_at"]),
            "odds": odds,
        }
    return result


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    freeze, digest = _load_verified_freeze()
    core = extract_core_top1(freeze, expected_core_races=6)
    race_ids = [str(row["race_id"]) for row in core]

    print("CANDIDATE_MARKET_FORWARD_MODE=immutable_v4_freeze_annotation", flush=True)
    print(f"CANDIDATE_MARKET_FORWARD_SOURCE_SHA256={digest}", flush=True)
    print(f"CANDIDATE_MARKET_FORWARD_FREEZE_RUN={FREEZE_RUN_ID} ARTIFACT={FREEZE_ARTIFACT_ID}", flush=True)
    print(f"CANDIDATE_MARKET_FORWARD_PROSPECTIVE_START={PROSPECTIVE_START}", flush=True)
    print("CANDIDATE_MARKET_FORWARD_RESULT_READ=0 DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='10s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
        labels = _fetch_valid_labels(conn, race_ids)
        odds_by_race = _fetch_snapshot_odds(conn, labels)
        conn.rollback()

    market_by_race = _market_input(labels, odds_by_race)
    annotated = annotate_feed(freeze, market_by_race, expected_core_races=6)
    if annotated["core_top1"] != 6 or annotated.get("exact_v4_source") is not True:
        raise RuntimeError("fail closed: exact six-race V4 source contract required")
    if any(not bool(row.get("counts_as_prospective")) for row in annotated["rows"]):
        raise RuntimeError("fail closed: non-prospective row reached prospective annotator")

    for row in annotated["rows"]:
        label = labels.get(str(row["race_id"]))
        row["snapshot_label"] = str(label["snapshot_label"]) if label else None
        row["snapshot_at"] = str(label["last_snapshot_at"]) if label else None
        row["lead_minutes"] = round(float(label["lead_minutes"]), 3) if label else None
        row["spread_seconds"] = round(float(label["spread_seconds"]), 3) if label else None

    out = {
        "contract": "MKT_LATE07_TOP2_SUPPORT_V1_FORWARD_ANNOTATION",
        "freeze_run_id": FREEZE_RUN_ID,
        "freeze_artifact_id": FREEZE_ARTIFACT_ID,
        "freeze_json_sha256": digest,
        "source_feed_contract": V4_FEED_CONTRACT,
        "annotation": annotated,
        "result_read": False,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        "CANDIDATE_MARKET_FORWARD_COVERAGE="
        f"core_top1:{annotated['core_top1']} late_available:{annotated['late_available']} "
        f"top2_supported:{annotated['top2_supported']}",
        flush=True,
    )
    for row in annotated["rows"]:
        print("CANDIDATE_MARKET_FORWARD_ROW=" + json.dumps(row, ensure_ascii=False, sort_keys=True), flush=True)
    print("CANDIDATE_MARKET_FORWARD_PROMOTION=BLOCK_RESEARCH_ONLY", flush=True)
    print("CANDIDATE_MARKET_FORWARD_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
