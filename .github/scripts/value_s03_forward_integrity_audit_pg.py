# -*- coding: utf-8 -*-
"""Independent read-only integrity audit for S03_FORWARD_V1 rows.

This validates stored prospective evidence; it does not reconstruct candidate
selection, retune any rule, or alter Production.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

START = date(2026, 9, 13)
END = date.fromisoformat(os.getenv("S03_FORWARD_END", "2026-09-27"))
JST = ZoneInfo("Asia/Tokyo")
OUTPUT = Path(os.getenv("S03_INTEGRITY_OUTPUT", "s03-forward-integrity-audit.json"))

EXPECTED = {
    "rule_id": "S03",
    "prob_rank_min": 11,
    "prob_rank_max": 25,
    "market_rank_min": 6,
    "market_rank_max": 10,
    "odds_min": 30.0,
    "odds_max_exclusive": 50.0,
    "race_nos": [7, 8, 9],
    "venue_style": "standard",
    "select_mode": "ev",
    "selection_policy": "latest_by_race_rule",
}


def jst(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=JST)
    return value.astimezone(JST)


def norm_ticket(value: Any) -> str:
    return str(value or "").strip().replace("=", "-").replace(">", "-").replace(" ", "")


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print("S03_INTEGRITY_POLICY=INDEPENDENT_STORED_FORWARD_EVIDENCE_AUDIT", flush=True)
    print("S03_INTEGRITY_RECONSTRUCT_SELECTION=0 RETUNE=0", flush=True)
    print("S03_INTEGRITY_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='60s'")
            cur.execute(
                """
                select s.id,s.race_id,s.race_date,s.venue_id,s.race_no,s.window_name,
                       s.rule_id,s.ticket,s.odds,s.prob,s.prob_rank,s.market_rank,
                       s.raw_ev,s.venue_style,s.event_category,s.snapshot_at,
                       s.hit,s.return_yen,s.evaluated_at,s.evaluation_status,s.evaluation_note,s.raw,
                       r.deadline_at,
                       x.result_status,x.race_status,x.trifecta_ticket,x.trifecta_payout_yen
                  from v2_candidate_filter_shadow s
                  join v2_races r on r.race_id=s.race_id
                  left join v2_results x on x.race_id=s.race_id
                 where s.rule_id='S03'
                   and s.race_date between %s and %s
                 order by s.race_date,s.race_id
                """,
                (START, END),
            )
            rows = [dict(r) for r in cur.fetchall()]
        conn.rollback()

    seen: set[str] = set()
    hard_errors: list[dict[str, Any]] = []
    raw_errors: list[dict[str, Any]] = []
    settlement_errors: list[dict[str, Any]] = []
    pending = evaluated = official_evaluated = expected_invalid_result = 0
    lead_minutes: list[float] = []

    def hard(row: dict[str, Any], reason: str) -> None:
        hard_errors.append({"race_id": str(row.get("race_id")), "reason": reason})

    for row in rows:
        rid = str(row.get("race_id") or "")
        if rid in seen:
            hard(row, "duplicate_race_id")
        seen.add(rid)

        if str(row.get("rule_id") or "") != "S03":
            hard(row, "rule_id")
        try:
            race_no = int(row.get("race_no"))
        except Exception:
            race_no = -1
        if race_no not in {7, 8, 9}:
            hard(row, "race_no")
        if str(row.get("venue_style") or "") != "standard":
            hard(row, "venue_style")

        try:
            pr = int(row.get("prob_rank"))
        except Exception:
            pr = -1
        try:
            mr = int(row.get("market_rank"))
        except Exception:
            mr = -1
        odd = as_float(row.get("odds"))
        if not (11 <= pr <= 25):
            hard(row, "prob_rank")
        if not (6 <= mr <= 10):
            hard(row, "market_rank")
        if odd is None or not (30.0 <= odd < 50.0):
            hard(row, "odds")

        snap = jst(row.get("snapshot_at"))
        deadline = jst(row.get("deadline_at"))
        if snap is None or deadline is None or not snap < deadline:
            hard(row, "snapshot_not_before_deadline")
        else:
            lead_minutes.append((deadline - snap).total_seconds() / 60.0)

        raw = row.get("raw")
        if not isinstance(raw, dict):
            raw_errors.append({"race_id": rid, "reason": "raw_not_object"})
        else:
            rule = raw.get("rule")
            if not isinstance(rule, dict):
                raw_errors.append({"race_id": rid, "reason": "raw_rule_missing"})
            else:
                checks = {
                    "pr_min": 11, "pr_max": 25,
                    "mr_min": 6, "mr_max": 10,
                    "odds_min": 30.0, "odds_max": 50.0,
                    "venue_style": "standard",
                    "event_category": "ALL",
                    "select_mode": "ev",
                }
                for key, expected in checks.items():
                    if rule.get(key) != expected:
                        raw_errors.append({"race_id": rid, "reason": f"raw_rule_{key}", "value": rule.get(key)})
                if sorted(rule.get("race_nos") or []) != [7, 8, 9]:
                    raw_errors.append({"race_id": rid, "reason": "raw_rule_race_nos", "value": rule.get("race_nos")})
            if raw.get("selection_policy") != "latest_by_race_rule":
                raw_errors.append({"race_id": rid, "reason": "selection_policy", "value": raw.get("selection_policy")})
            if raw.get("selector_source") != "v24_probability_model":
                raw_errors.append({"race_id": rid, "reason": "selector_source", "value": raw.get("selector_source")})

        status = str(row.get("evaluation_status") or "")
        official = (
            str(row.get("result_status") or "").lower() == "official"
            and str(row.get("race_status") or "").lower() == "official"
        )

        if status == "invalid_result":
            expected_invalid_result += 1
            if official:
                settlement_errors.append({"race_id": rid, "reason": "invalid_result_but_official"})
            if bool(row.get("hit")) or int(row.get("return_yen") or 0) != 0:
                settlement_errors.append({"race_id": rid, "reason": "invalid_result_nonzero_settlement"})
            continue

        is_eval = status == "evaluated"
        if not is_eval:
            pending += 1
            continue
        evaluated += 1

        if not official:
            settlement_errors.append({"race_id": rid, "reason": "evaluated_without_official_result"})
            continue
        official_evaluated += 1

        selected = norm_ticket(row.get("ticket"))
        actual = norm_ticket(row.get("trifecta_ticket"))
        expected_hit = selected == actual and bool(selected)
        stored_hit = bool(row.get("hit"))
        if stored_hit != expected_hit:
            settlement_errors.append({
                "race_id": rid, "reason": "hit_mismatch",
                "selected": selected, "actual": actual,
                "stored_hit": stored_hit, "expected_hit": expected_hit,
            })
        payout = int(row.get("trifecta_payout_yen") or 0)
        expected_return = payout if expected_hit else 0
        stored_return = int(row.get("return_yen") or 0)
        if stored_return != expected_return:
            settlement_errors.append({
                "race_id": rid, "reason": "return_mismatch",
                "stored_return": stored_return, "expected_return": expected_return,
                "payout": payout,
            })

    classification = "CONTRACT_CLEAN"
    if hard_errors or settlement_errors:
        classification = "HARD_INTEGRITY_FAILURE"
    elif raw_errors:
        classification = "RAW_METADATA_DRIFT_ONLY"

    out = {
        "contract": "s03_forward_integrity_audit_v1",
        "period": {"start": START.isoformat(), "end": END.isoformat()},
        "expected": EXPECTED,
        "coverage": {
            "rows": len(rows),
            "unique_race_ids": len(seen),
            "evaluated": evaluated,
            "pending": pending,
            "official_evaluated": official_evaluated,
            "expected_invalid_result": expected_invalid_result,
            "min_minutes_before_deadline": round(min(lead_minutes), 3) if lead_minutes else None,
            "median_minutes_before_deadline": round(sorted(lead_minutes)[len(lead_minutes)//2], 3) if lead_minutes else None,
        },
        "hard_errors": hard_errors,
        "raw_metadata_errors": raw_errors,
        "settlement_errors": settlement_errors,
        "selection_reconstruction_performed": False,
        "selection_reconstruction_limitation": (
            "Historical all-ticket candidate sets / same-snapshot odds are not reconstructed. "
            "This audit validates the stored frozen row and official settlement only."
        ),
        "classification": classification,
        "safety": {
            "db_write": False, "line": False, "buy": False,
            "production_change": False, "promotion_allowed": False,
        },
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print("S03_INTEGRITY_COVERAGE=" + json.dumps(out["coverage"], sort_keys=True), flush=True)
    print(f"S03_INTEGRITY_HARD_ERRORS={len(hard_errors)}", flush=True)
    print(f"S03_INTEGRITY_RAW_METADATA_ERRORS={len(raw_errors)}", flush=True)
    print(f"S03_INTEGRITY_SETTLEMENT_ERRORS={len(settlement_errors)}", flush=True)
    print("S03_INTEGRITY_SETTLEMENT_ERROR_SAMPLE=" + json.dumps(settlement_errors[:20], sort_keys=True), flush=True)
    print(f"S03_INTEGRITY_CLASSIFICATION={classification}", flush=True)
    print("S03_INTEGRITY_PROMOTION_ALLOWED=0", flush=True)
    print("S03_INTEGRITY_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
