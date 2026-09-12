# -*- coding: utf-8 -*-
"""Read-only prospective audit for the frozen S03_M2_POSITIVE_V1 contract.

Freeze date: 2026-09-12 JST
Prospective start: 2026-09-13 JST

This script must not tune the rule from post-freeze outcomes. A materially
changed rule requires a new contract/version and a new prospective start date.
No DB writes / LINE / BUY / Production behavior changes.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

CONTRACT = "S03_M2_POSITIVE_V1"
START_DATE = date(2026, 9, 13)
END_DATE = date.fromisoformat(os.environ["VALUE_S03_M2_FORWARD_END"]) if os.getenv("VALUE_S03_M2_FORWARD_END") else datetime.now(ZoneInfo("Asia/Tokyo")).date()
OUTPUT = Path(os.getenv("VALUE_S03_M2_FORWARD_OUTPUT", "value-s03-m2-forward-frozen.json"))
BETA = 0.06
POS_W = (1.0, 0.6, 0.3)
SCORE_BOUNDARY = 0.0
UNIT_YEN = 100
CHECKPOINTS = (30, 50, 100)

FROZEN_CONFIG = {
    "contract": CONTRACT,
    "prospective_start": START_DATE.isoformat(),
    "source_rule_id": "S03",
    "feature": "motor_place2_rate",
    "position_weights": list(POS_W),
    "beta": BETA,
    "score_operator": ">",
    "score_boundary": SCORE_BOUNDARY,
    "unit_yen": UNIT_YEN,
    "checkpoints": list(CHECKPOINTS),
}
FROZEN_CONFIG_SHA256 = hashlib.sha256(
    json.dumps(FROZEN_CONFIG, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


def si(v: Any, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except Exception:
        return default


def sf(v: Any, default: float | None = None) -> float | None:
    try:
        if v in (None, ""):
            return default
        return float(v)
    except Exception:
        return default


def ticket_lanes(value: Any) -> tuple[int, int, int] | None:
    xs = [int(x) for x in re.findall(r"[1-6]", str(value or ""))]
    if len(xs) < 3 or len(set(xs[:3])) != 3:
        return None
    return xs[0], xs[1], xs[2]


def score_for(entries: list[dict[str, Any]], ticket: Any) -> float | None:
    lanes = ticket_lanes(ticket)
    if lanes is None:
        return None
    by = {si(e.get("lane")): e for e in entries}
    if set(by) != {1, 2, 3, 4, 5, 6}:
        return None
    vals: list[float] = []
    for lane in range(1, 7):
        x = sf(by[lane].get("motor_place2_rate"))
        if x is None or not 0.0 <= x <= 100.0:
            return None
        vals.append(float(x))
    mu = sum(vals) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / 6.0)
    if sd < 1e-12:
        return None
    z = {lane: (vals[lane - 1] - mu) / sd for lane in range(1, 7)}
    a, b, c = lanes
    return POS_W[0] * z[a] + POS_W[1] * z[b] + POS_W[2] * z[c]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [r for r in rows if r.get("hit") is not None and r.get("return_yen") is not None]
    pending = len(rows) - len(evaluated)
    hits = sum(1 for r in evaluated if bool(r.get("hit")))
    returned = sum(si(r.get("return_yen"), 0) for r in evaluated)
    invested = len(evaluated) * UNIT_YEN
    hit_returns = sorted((si(r.get("return_yen"), 0) for r in evaluated if bool(r.get("hit"))), reverse=True)
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evaluated:
        by_month[str(row.get("race_date"))[:7]].append(row)
    monthly: dict[str, dict[str, Any]] = {}
    for month, rr in sorted(by_month.items()):
        ret = sum(si(r.get("return_yen"), 0) for r in rr)
        inv = len(rr) * UNIT_YEN
        monthly[month] = {
            "evaluated": len(rr),
            "hits": sum(1 for r in rr if bool(r.get("hit"))),
            "investment_yen": inv,
            "return_yen": ret,
            "profit_yen": ret - inv,
            "roi_pct": round(ret / inv * 100.0, 4) if inv else None,
        }
    return {
        "eligible_rows": len(rows),
        "evaluated": len(evaluated),
        "pending": pending,
        "hits": hits,
        "hit_rate_pct": round(hits / len(evaluated) * 100.0, 4) if evaluated else None,
        "investment_yen": invested,
        "return_yen": returned,
        "profit_yen": returned - invested,
        "roi_pct": round(returned / invested * 100.0, 4) if invested else None,
        "max_hit_yen": hit_returns[0] if hit_returns else 0,
        "single_hit_share_pct": round(hit_returns[0] / returned * 100.0, 4) if hit_returns and returned else 0.0,
        "by_month": monthly,
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"VALUE_S03_M2_FORWARD_CONTRACT={CONTRACT}", flush=True)
    print(f"VALUE_S03_M2_FORWARD_CONFIG_SHA256={FROZEN_CONFIG_SHA256}", flush=True)
    print(f"VALUE_S03_M2_FORWARD_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("VALUE_S03_M2_FORWARD_POLICY=frozen_no_retune_read_only_no_prod_change", flush=True)
    print("VALUE_S03_M2_FORWARD_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0 PROMOTION=0", flush=True)

    shadow: list[dict[str, Any]] = []
    entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if END_DATE >= START_DATE:
        with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
            with conn.cursor() as cur:
                cur.execute("set transaction read only")
                cur.execute("set local statement_timeout='120s'")
                cur.execute(
                    """select race_id,race_date,rule_id,ticket,snapshot_at,hit,return_yen,evaluated_at
                         from v2_candidate_filter_shadow
                        where race_date between %s and %s
                          and rule_id='S03'
                        order by race_date,race_id""",
                    (START_DATE, END_DATE),
                )
                shadow = [dict(r) for r in cur.fetchall()]
                race_ids = sorted({str(r["race_id"]) for r in shadow})
                if race_ids:
                    cur.execute(
                        """select race_id,lane,motor_place2_rate
                             from v2_race_entries
                            where race_id = any(%s)
                            order by race_id,lane""",
                        (race_ids,),
                    )
                    for row in cur.fetchall():
                        entries[str(row["race_id"])].append(dict(row))
            conn.rollback()

    eligible: list[dict[str, Any]] = []
    missing_motor = 0
    nonpositive = 0
    for row in shadow:
        score = score_for(entries.get(str(row["race_id"]), []), row.get("ticket"))
        if score is None:
            missing_motor += 1
            continue
        if score <= SCORE_BOUNDARY:
            nonpositive += 1
            continue
        x = dict(row)
        x["motor2_score"] = score
        x["motor2_factor"] = math.exp(BETA * score)
        eligible.append(x)

    stats = summarize(eligible)
    checkpoints = {
        str(n): {
            "target_evaluated": n,
            "reached": int(stats["evaluated"]) >= n,
            "remaining": max(0, n - int(stats["evaluated"])),
        }
        for n in CHECKPOINTS
    }
    out = {
        "frozen_config": FROZEN_CONFIG,
        "frozen_config_sha256": FROZEN_CONFIG_SHA256,
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat()},
        "audit": {
            "source_s03_rows": len(shadow),
            "missing_motor_rows": missing_motor,
            "nonpositive_rows": nonpositive,
        },
        "forward": stats,
        "checkpoints": checkpoints,
        "mutation_performed": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    print("VALUE_S03_M2_FORWARD_AUDIT=" + json.dumps(out["audit"], sort_keys=True), flush=True)
    print(
        "VALUE_S03_M2_FORWARD_STATS="
        f"eligible:{stats['eligible_rows']} evaluated:{stats['evaluated']} pending:{stats['pending']} "
        f"hits:{stats['hits']} roi:{stats['roi_pct']} profit:{stats['profit_yen']} "
        f"single_hit_share:{stats['single_hit_share_pct']}",
        flush=True,
    )
    for n in CHECKPOINTS:
        cp = checkpoints[str(n)]
        print(
            f"VALUE_S03_M2_FORWARD_CHECKPOINT={n} reached:{int(cp['reached'])} remaining:{cp['remaining']}",
            flush=True,
        )
    print("VALUE_S03_M2_FORWARD_PROMOTION_ALLOWED=0", flush=True)
    print("VALUE_S03_M2_FORWARD_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
