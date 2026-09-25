# -*- coding: utf-8 -*-
"""Post-freeze diagnostics for S03_M2_POSITIVE_V1.

This script does not alter the frozen rule. It imports the exact score/config
from value_s03_m2_forward_frozen_pg.py and only adds risk/complement reporting
for the already-frozen 2026-09-13 onward Forward sample.

Research-only: READ ONLY DB, no threshold search, no Production changes.
"""
from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

import psycopg
from psycopg.rows import dict_row

import value_s03_m2_forward_frozen_pg as frozen

END_DATE = date.fromisoformat(
    os.getenv("VALUE_S03_M2_DIAG_END", "2026-09-23")
)
OUTPUT = Path(
    os.getenv(
        "VALUE_S03_M2_DIAG_OUTPUT",
        "value-s03-m2-forward-diagnostics.json",
    )
)
BOOTSTRAP_SAMPLES = int(
    os.getenv("VALUE_S03_M2_DIAG_BOOTSTRAP_SAMPLES", "20000")
)
BOOTSTRAP_SEED = int(
    os.getenv("VALUE_S03_M2_DIAG_BOOTSTRAP_SEED", "20260923")
)
UNIT_YEN = frozen.UNIT_YEN


def evaluated(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in rows
        if row.get("hit") is not None and row.get("return_yen") is not None
    ]


def risk_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(
        evaluated(rows),
        key=lambda row: (str(row.get("race_date")), str(row.get("race_id"))),
    )
    equity = peak = max_dd = losing = max_losing = 0
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hit_returns = []
    for row in ordered:
        ret = frozen.si(row.get("return_yen"), 0)
        equity += ret - UNIT_YEN
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        if bool(row.get("hit")):
            losing = 0
            hit_returns.append(ret)
        else:
            losing += 1
            max_losing = max(max_losing, losing)
        by_day[str(row.get("race_date"))].append(row)

    daily = []
    for day, rr in sorted(by_day.items()):
        inv = len(rr) * UNIT_YEN
        ret = sum(frozen.si(row.get("return_yen"), 0) for row in rr)
        daily.append(
            {
                "date": day,
                "bets": len(rr),
                "investment_yen": inv,
                "return_yen": ret,
            }
        )

    return {
        "max_losing_streak": max_losing,
        "max_drawdown_yen": max_dd,
        "ending_profit_yen": equity,
        "hit_returns_yen": sorted(hit_returns, reverse=True),
        "daily": daily,
    }


def bootstrap_roi(daily: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not daily:
        return {
            "samples": BOOTSTRAP_SAMPLES,
            "seed": BOOTSTRAP_SEED,
            "p025": None,
            "median": None,
            "p975": None,
            "positive_share_percent": None,
        }
    rng = random.Random(BOOTSTRAP_SEED)
    values = []
    n = len(daily)
    for _ in range(BOOTSTRAP_SAMPLES):
        inv = ret = 0
        for _ in range(n):
            row = daily[rng.randrange(n)]
            inv += int(row["investment_yen"])
            ret += int(row["return_yen"])
        if inv:
            values.append(ret / inv * 100.0)
    values.sort()

    def q(p: float) -> float:
        idx = int(round((len(values) - 1) * p))
        return round(values[max(0, min(idx, len(values) - 1))], 3)

    return {
        "samples": BOOTSTRAP_SAMPLES,
        "seed": BOOTSTRAP_SEED,
        "p025": q(0.025),
        "median": q(0.5),
        "p975": q(0.975),
        "positive_share_percent": round(
            sum(1 for value in values if value > 100.0)
            / len(values)
            * 100.0,
            3,
        ),
    }


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(
        f"VALUE_S03_M2_DIAG_CONTRACT={frozen.CONTRACT} "
        f"CONFIG_SHA256={frozen.FROZEN_CONFIG_SHA256}",
        flush=True,
    )
    print(
        f"VALUE_S03_M2_DIAG_PERIOD={frozen.START_DATE}..{END_DATE}",
        flush=True,
    )
    print(
        "VALUE_S03_M2_DIAG_MODE=READ_ONLY_RULE_UNCHANGED_NO_RETUNE "
        "DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0",
        flush=True,
    )

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute(
                """select race_id,race_date,rule_id,ticket,snapshot_at,
                          hit,return_yen,evaluated_at
                     from v2_candidate_filter_shadow
                    where race_date between %s and %s
                      and rule_id='S03'
                    order by race_date,race_id""",
                (frozen.START_DATE, END_DATE),
            )
            source = [dict(row) for row in cur.fetchall()]
            race_ids = sorted({str(row["race_id"]) for row in source})
            entries: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if race_ids:
                cur.execute(
                    """select race_id,lane,motor_place2_rate
                         from v2_race_entries
                        where race_id=any(%s)
                        order by race_id,lane""",
                    (race_ids,),
                )
                for row in cur.fetchall():
                    entries[str(row["race_id"])].append(dict(row))
        conn.rollback()

    positive = []
    nonpositive = []
    missing = []
    for row in source:
        score = frozen.score_for(
            entries.get(str(row["race_id"]), []),
            row.get("ticket"),
        )
        item = dict(row)
        item["motor2_score"] = score
        if score is None:
            missing.append(item)
        elif score > frozen.SCORE_BOUNDARY:
            positive.append(item)
        else:
            nonpositive.append(item)

    source_stats = frozen.summarize(source)
    positive_stats = frozen.summarize(positive)
    nonpositive_stats = frozen.summarize(nonpositive)
    positive_risk = risk_summary(positive)
    nonpositive_risk = risk_summary(nonpositive)
    source_risk = risk_summary(source)
    positive_boot = bootstrap_roi(positive_risk["daily"])

    out = {
        "contract": "S03_M2_POSITIVE_V1_forward_diagnostics_v1",
        "frozen_config": frozen.FROZEN_CONFIG,
        "frozen_config_sha256": frozen.FROZEN_CONFIG_SHA256,
        "period": {
            "start": frozen.START_DATE.isoformat(),
            "end": END_DATE.isoformat(),
        },
        "partition": {
            "source_rows": len(source),
            "positive_rows": len(positive),
            "nonpositive_rows": len(nonpositive),
            "missing_rows": len(missing),
        },
        "source_s03": {
            "stats": source_stats,
            "risk": source_risk,
        },
        "m2_positive": {
            "stats": positive_stats,
            "risk": positive_risk,
            "day_bootstrap_roi_percent": positive_boot,
        },
        "m2_nonpositive": {
            "stats": nonpositive_stats,
            "risk": nonpositive_risk,
        },
        "interpretation": {
            "rule_changed": False,
            "score_boundary_changed": False,
            "beta_changed": False,
            "weights_changed": False,
            "promotion_allowed": False,
            "purchase_action": False,
        },
        "mutation_performed": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        + "\n",
        encoding="utf-8",
    )

    print(
        "VALUE_S03_M2_DIAG_SOURCE="
        f"evaluated:{source_stats['evaluated']} hits:{source_stats['hits']} "
        f"roi:{source_stats['roi_pct']} profit:{source_stats['profit_yen']} "
        f"max_dd:{source_risk['max_drawdown_yen']} "
        f"lose_streak:{source_risk['max_losing_streak']}",
        flush=True,
    )
    print(
        "VALUE_S03_M2_DIAG_POSITIVE="
        f"evaluated:{positive_stats['evaluated']} hits:{positive_stats['hits']} "
        f"roi:{positive_stats['roi_pct']} profit:{positive_stats['profit_yen']} "
        f"max_dd:{positive_risk['max_drawdown_yen']} "
        f"lose_streak:{positive_risk['max_losing_streak']} "
        f"boot_pos:{positive_boot['positive_share_percent']} "
        f"boot95:[{positive_boot['p025']},{positive_boot['p975']}]",
        flush=True,
    )
    print(
        "VALUE_S03_M2_DIAG_NONPOSITIVE="
        f"evaluated:{nonpositive_stats['evaluated']} hits:{nonpositive_stats['hits']} "
        f"roi:{nonpositive_stats['roi_pct']} profit:{nonpositive_stats['profit_yen']} "
        f"max_dd:{nonpositive_risk['max_drawdown_yen']} "
        f"lose_streak:{nonpositive_risk['max_losing_streak']}",
        flush=True,
    )
    print("VALUE_S03_M2_DIAG_PURCHASE_ACTION=false", flush=True)
    print("RESULT=PASS_READ_ONLY_S03_M2_DIAGNOSTICS", flush=True)


if __name__ == "__main__":
    main()
