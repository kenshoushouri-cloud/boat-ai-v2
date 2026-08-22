# -*- coding: utf-8 -*-
"""Odds-free historical replay of the current v24 120-ticket probability model.

The probability path receives only the historical race entries and venue id.
No odds table is queried. Results are fetched only after probabilities are
computed so they cannot influence the model output.

Read-only: no DB writes, no Production/Shadow/LINE changes.
"""
from __future__ import annotations

import math
import os
import re
from collections import defaultdict
from statistics import mean

import psycopg
from psycopg.rows import dict_row

import v24_pre_candidate_notifier_pg as v24

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DATES = ["2025-07-01", "2025-12-15", "2026-04-15", "2026-08-01"]
TOL = 1e-10


def norm_ticket(v) -> str:
    nums = re.findall(r"[1-6]", str(v or ""))
    return "-".join(nums[:3]) if len(nums) >= 3 else str(v or "").strip()


def main() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required")

    print("BAO_HPR_MODE=read_only_odds_free", flush=True)
    print("BAO_HPR_DATES=" + ",".join(DATES), flush=True)
    print("BAO_HPR_PROB_FUNC=v24._ticket_probabilities", flush=True)
    print("BAO_HPR_ODDS_QUERY=0", flush=True)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select r.race_id,r.race_date,
                       coalesce(r.venue_id,r.venue_code) as venue_id,
                       r.race_no
                from v2_races r
                where r.race_date = any(%s::date[])
                order by r.race_date,coalesce(r.venue_id,r.venue_code),r.race_no
                """,
                (DATES,),
            )
            races = [dict(x) for x in cur.fetchall()]

            cur.execute(
                """
                select e.race_id,e.lane,e.racer_number,e.racer_class,e.racer_name,
                       e.national_win_rate,e.national_place2_rate,
                       e.local_win_rate,e.local_place2_rate,e.avg_st,
                       e.motor_no,e.boat_no
                from v2_race_entries e
                join v2_races r on r.race_id=e.race_id
                where r.race_date = any(%s::date[])
                order by e.race_id,e.lane
                """,
                (DATES,),
            )
            entries = [dict(x) for x in cur.fetchall()]

    by_race = defaultdict(list)
    for e in entries:
        by_race[str(e["race_id"])].append(e)

    predictions = {}
    malformed = incomplete = sum_fail = nonpositive = 0
    date_counts = defaultdict(lambda: {"races": 0, "complete": 0})

    # IMPORTANT: probability calculation happens before results are fetched.
    for r in races:
        rid = str(r["race_id"])
        ds = str(r["race_date"])
        date_counts[ds]["races"] += 1
        es = by_race.get(rid, [])
        lanes = {int(e.get("lane") or 0) for e in es}
        if len(es) != 6 or lanes != {1, 2, 3, 4, 5, 6}:
            incomplete += 1
            continue
        venue = str(r.get("venue_id") or "").zfill(2)
        try:
            probs = v24._ticket_probabilities(es, venue)
        except Exception as exc:
            print(f"BAO_HPR_ERROR=race:{rid} type:{type(exc).__name__}", flush=True)
            malformed += 1
            continue
        tickets = set(probs)
        expected = {f"{a}-{b}-{c}" for a in range(1,7) for b in range(1,7) for c in range(1,7) if len({a,b,c}) == 3}
        if len(probs) != 120 or tickets != expected:
            malformed += 1
            continue
        s = sum(float(p) for p in probs.values())
        if abs(s - 1.0) > TOL:
            sum_fail += 1
            continue
        if any((not math.isfinite(float(p))) or float(p) <= 0 for p in probs.values()):
            nonpositive += 1
            continue
        predictions[rid] = {
            "date": ds,
            "venue": venue,
            "race_no": int(r.get("race_no") or 0),
            "probs": probs,
            "sum": s,
        }
        date_counts[ds]["complete"] += 1

    # Results are intentionally read only after all probability dictionaries exist.
    with psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select res.race_id,res.trifecta_ticket
                from v2_results res
                join v2_races r on r.race_id=res.race_id
                where r.race_date = any(%s::date[])
                """,
                (DATES,),
            )
            results = {str(x["race_id"]): norm_ticket(x["trifecta_ticket"]) for x in cur.fetchall()}

    evaluated = []
    for rid, pred in predictions.items():
        actual = results.get(rid, "")
        if actual not in pred["probs"]:
            continue
        probs = pred["probs"]
        p_actual = float(probs[actual])
        ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
        actual_rank = 1 + next(i for i, (t, _) in enumerate(ranked) if t == actual)
        multiclass_brier = sum((float(p) - (1.0 if t == actual else 0.0)) ** 2 for t, p in probs.items())
        logloss = -math.log(max(p_actual, 1e-15))
        evaluated.append({
            "race_id": rid,
            "date": pred["date"],
            "p_actual": p_actual,
            "rank": actual_rank,
            "brier": multiclass_brier,
            "logloss": logloss,
        })

    for ds in DATES:
        xs = [x for x in evaluated if x["date"] == ds]
        c = date_counts[ds]
        if xs:
            print(
                f"BAO_HPR_DATE={ds} races:{c['races']} complete:{c['complete']} evaluated:{len(xs)} "
                f"mean_p_actual:{mean(x['p_actual'] for x in xs):.6f} "
                f"mean_rank:{mean(x['rank'] for x in xs):.2f} "
                f"top1:{sum(x['rank']<=1 for x in xs)}/{len(xs)} "
                f"top3:{sum(x['rank']<=3 for x in xs)}/{len(xs)} "
                f"top10:{sum(x['rank']<=10 for x in xs)}/{len(xs)} "
                f"brier:{mean(x['brier'] for x in xs):.6f} logloss:{mean(x['logloss'] for x in xs):.6f}",
                flush=True,
            )
        else:
            print(f"BAO_HPR_DATE={ds} races:{c['races']} complete:{c['complete']} evaluated:0", flush=True)

    print(
        f"BAO_HPR_STRUCTURE=predicted:{len(predictions)} evaluated:{len(evaluated)} incomplete:{incomplete} "
        f"malformed:{malformed} sum_fail:{sum_fail} nonpositive:{nonpositive}",
        flush=True,
    )
    if evaluated:
        print(
            f"BAO_HPR_ALL=n:{len(evaluated)} mean_p_actual:{mean(x['p_actual'] for x in evaluated):.6f} "
            f"mean_rank:{mean(x['rank'] for x in evaluated):.2f} "
            f"top1:{sum(x['rank']<=1 for x in evaluated)}/{len(evaluated)} "
            f"top3:{sum(x['rank']<=3 for x in evaluated)}/{len(evaluated)} "
            f"top10:{sum(x['rank']<=10 for x in evaluated)}/{len(evaluated)} "
            f"brier:{mean(x['brier'] for x in evaluated):.6f} logloss:{mean(x['logloss'] for x in evaluated):.6f}",
            flush=True,
        )

    structural_pass = len(predictions) > 0 and malformed == 0 and sum_fail == 0 and nonpositive == 0
    coverage_pass = all(date_counts[d]["complete"] > 0 for d in DATES)
    print(f"BAO_HPR_STRUCTURAL_PASS={int(structural_pass)}", flush=True)
    print(f"BAO_HPR_DATE_COVERAGE_PASS={int(coverage_pass)}", flush=True)
    if not structural_pass or not coverage_pass:
        print("BAO_HPR_RESULT=FAIL", flush=True)
        raise SystemExit(2)
    print("BAO_HPR_NEXT=small_window_then_monthly_odds_separated_replay", flush=True)
    print("BAO_HPR_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
