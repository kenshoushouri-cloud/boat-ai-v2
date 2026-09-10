# -*- coding: utf-8 -*-
"""Read-only fixed Forward audit for Racer Course Top3 + Opponent Pressure.

Fixed contract:
- BASE/COURSE are frozen ticket distributions from racer-course Forward Shadow.
- Course coefficient stays 0.50.
- Opponent coefficient stays 1.0 using stored (adj_win - base_win).
- Opponent Pressure changes only the first-place marginal; the source
  conditional P(second, third | first) is preserved.
- No coefficient search, subgroup selection, DB writes, or Production change.
"""
from __future__ import annotations

import math
import os
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

JST = timezone(timedelta(hours=9))
START_DATE = date.fromisoformat(os.getenv("COURSE_OPP_COMBINED_START", "2026-08-25"))
END_DATE = date.fromisoformat(os.getenv("COURSE_OPP_COMBINED_END", "2026-09-10"))
COURSE_COEF = 0.50
OPP_COEF = 1.0
SOURCE_CUTOFF = time(8, 15)
EPS = 1e-15
BOOT_REPS = int(os.getenv("COURSE_OPP_BOOT_REPS", "5000"))
BOOT_SEED = 20260910
TICKETS = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7) if b != a
    for c in range(1, 7) if c not in (a, b)
)
TICKET_INDEX = {t: i for i, t in enumerate(TICKETS)}
HEAD_INDEX = [int(t[0]) - 1 for t in TICKETS]


def aware_jst(v: Any) -> datetime | None:
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=JST)
    return v.astimezone(JST)


def valid_probs(xs: Any, n: int) -> bool:
    if not isinstance(xs, list) or len(xs) != n:
        return False
    try:
        vals = [float(x) for x in xs]
    except Exception:
        return False
    return all(math.isfinite(x) and x >= 0.0 for x in vals) and abs(sum(vals) - 1.0) <= 5e-5


def normalize(xs: list[float]) -> list[float]:
    vals = [max(EPS, float(x)) for x in xs]
    total = sum(vals)
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("invalid normalization total")
    return [x / total for x in vals]


def first_marginal(ticket_probs: list[float]) -> list[float]:
    out = [0.0] * 6
    for i, p in enumerate(ticket_probs):
        out[HEAD_INDEX[i]] += float(p)
    return out


def apply_first_place_delta(ticket_probs: list[float], pressure_delta: list[float]) -> list[float]:
    """Adjust P(first) and preserve P(second,third | first)."""
    if len(ticket_probs) != 120 or len(pressure_delta) != 6:
        raise ValueError("bad probability dimensions")
    base_first = first_marginal(ticket_probs)
    if any(x <= 0.0 or not math.isfinite(x) for x in base_first):
        raise ValueError("invalid first-place marginal")
    target_first = normalize([
        max(EPS, min(0.999, base_first[i] + OPP_COEF * float(pressure_delta[i])))
        for i in range(6)
    ])
    factors = [target_first[i] / base_first[i] for i in range(6)]
    adjusted = [float(p) * factors[HEAD_INDEX[i]] for i, p in enumerate(ticket_probs)]
    return normalize(adjusted)


def metric(probs: list[float], actual: str) -> tuple[float, float, float]:
    idx = TICKET_INDEX[actual]
    p = max(float(probs[idx]), EPS)
    target = float(probs[idx])
    rank = 1 + sum(
        1 for i, x in enumerate(probs)
        if float(x) > target or (float(x) == target and i < idx)
    )
    brier = sum((float(x) - (1.0 if i == idx else 0.0)) ** 2 for i, x in enumerate(probs))
    return -math.log(p), brier, float(rank)


def aggregate(records: list[dict[str, Any]], model: str) -> tuple[float, float, float]:
    n = len(records)
    if not n:
        return 0.0, 0.0, 0.0
    return tuple(sum(r[model][i] for r in records) / n for i in range(3))


def emit_model(name: str, values: tuple[float, float, float], base: tuple[float, float, float]) -> None:
    print(
        f"COURSE_OPP_COMBINED_MODEL={name} ll:{values[0]:.8f} brier:{values[1]:.8f} rank:{values[2]:.4f} "
        f"delta_ll_vs_base:{values[0]-base[0]:+.8f} delta_brier_vs_base:{values[1]-base[1]:+.8f} "
        f"delta_rank_vs_base:{values[2]-base[2]:+.4f}", flush=True,
    )


def quantile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    pos = (len(sorted_values) - 1) * q
    lo = int(math.floor(pos)); hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_values[lo]
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def bootstrap_ci(records: list[dict[str, Any]]) -> list[tuple[float, float, float]]:
    """Paired bootstrap of COMBINED - COURSE for ll/brier/rank."""
    n = len(records)
    if n == 0 or BOOT_REPS <= 0:
        return [(0.0, 0.0, 0.0)] * 3
    deltas = [[r["COMBINED"][i] - r["COURSE"][i] for r in records] for i in range(3)]
    rng = random.Random(BOOT_SEED)
    reps = [[] for _ in range(3)]
    for _ in range(BOOT_REPS):
        sums = [0.0, 0.0, 0.0]
        for _j in range(n):
            k = rng.randrange(n)
            for i in range(3):
                sums[i] += deltas[i][k]
        for i in range(3):
            reps[i].append(sums[i] / n)
    out = []
    for vals in reps:
        vals.sort()
        out.append((sum(vals) / len(vals), quantile(vals, 0.025), quantile(vals, 0.975)))
    return out


def load_rows(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("set transaction read only")
        cur.execute("set local statement_timeout='120s'")
        cur.execute("set local lock_timeout='5s'")
        cur.execute("set local idle_in_transaction_session_timeout='30s'")
        cur.execute(
            """
            select c.race_id,c.race_date,c.venue_id,c.race_no,
                   c.model_version as course_model_version,c.formula_version,
                   c.ticket_order_version,c.course_coef,c.source_cutoff_jst,
                   c.deadline_at,c.snapshot_at,c.minutes_before,c.course_top3_rates,
                   c.course_snapshot_ats,c.base_probs,c.course_probs,
                   o.model_version as opp_model_version,o.train_end,o.matched_opponents,
                   o.base_win,o.adj_win,o.created_at as opp_created_at,
                   r.result_status,r.race_status,r.trifecta_ticket
              from v2_racer_course_top3_forward_shadow c
              join v2_opponent_pressure_shadow_v2 o on o.race_id=c.race_id
              left join v2_results r on r.race_id=c.race_id
             where c.race_date between %s and %s
             order by c.race_date,c.venue_id,c.race_no,c.race_id
            """,
            (START_DATE, END_DATE),
        )
        return [dict(x) for x in cur.fetchall()]


def course_integrity(row: dict[str, Any]) -> bool:
    race_date = row.get("race_date")
    deadline = aware_jst(row.get("deadline_at"))
    snapshot = aware_jst(row.get("snapshot_at"))
    source_times = row.get("course_snapshot_ats")
    rates = row.get("course_top3_rates")
    return bool(
        int(row.get("course_model_version") or 0) == 1
        and abs(float(row.get("course_coef") or 0.0) - COURSE_COEF) < 1e-9
        and str(row.get("source_cutoff_jst") or "") == "08:15"
        and str(row.get("ticket_order_version") or "") == "lexicographic_lane_loop_120_fixed_v1"
        and isinstance(rates, list) and len(rates) == 6
        and all(math.isfinite(float(x)) and 0.0 <= float(x) <= 100.0 for x in rates)
        and valid_probs(row.get("base_probs"), 120)
        and valid_probs(row.get("course_probs"), 120)
        and isinstance(source_times, list) and len(source_times) == 6
        and race_date is not None and deadline is not None and snapshot is not None
        and snapshot < deadline and float(row.get("minutes_before") or 0.0) >= 3.0
        and all(
            (dt := aware_jst(raw)) is not None
            and dt.date() == race_date
            and dt.time().replace(tzinfo=None) <= SOURCE_CUTOFF
            and dt < deadline
            for raw in source_times
        )
    )


def opponent_integrity(row: dict[str, Any]) -> bool:
    race_date = row.get("race_date")
    deadline = aware_jst(row.get("deadline_at"))
    created = aware_jst(row.get("opp_created_at"))
    matched = row.get("matched_opponents"); base_win = row.get("base_win"); adj_win = row.get("adj_win")
    try:
        arrays_ok = (
            isinstance(matched, list) and len(matched) == 6 and all(int(x) >= 4 for x in matched)
            and isinstance(base_win, list) and len(base_win) == 6
            and isinstance(adj_win, list) and len(adj_win) == 6
            and all(math.isfinite(float(x)) and 0.0 < float(x) < 1.0 for x in base_win + adj_win)
        )
    except Exception:
        arrays_ok = False
    return bool(
        int(row.get("opp_model_version") or 0) == 2
        and race_date is not None and row.get("train_end") is not None and row.get("train_end") < race_date
        and deadline is not None and created is not None and created.date() == race_date and created < deadline
        and arrays_ok
    )


def group_stability(records: list[dict[str, Any]], key: str) -> tuple[int, int, int, int, int]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in records:
        groups[str(r[key])].append(r)
    all3 = ll = br = rk = 0
    for rows in groups.values():
        c = aggregate(rows, "COURSE"); x = aggregate(rows, "COMBINED")
        ll += x[0] < c[0]; br += x[1] < c[1]; rk += x[2] < c[2]
        all3 += x[0] < c[0] and x[1] < c[1] and x[2] < c[2]
    return len(groups), ll, br, rk, all3


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    if END_DATE < START_DATE:
        raise RuntimeError("end before start")
    print("COURSE_OPP_COMBINED_MODE=read_only_fixed_forward_no_tuning", flush=True)
    print(f"COURSE_OPP_COMBINED_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("COURSE_OPP_COMBINED_COURSE_COEF=0.50_fixed", flush=True)
    print("COURSE_OPP_COMBINED_OPP_COEF=1.0_fixed_first_place_delta", flush=True)
    print("COURSE_OPP_COMBINED_METHOD=preserve_conditional_second_third_given_first", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        rows = load_rows(conn)
        conn.rollback()

    records: list[dict[str, Any]] = []
    invalid_course = invalid_opp = pending = invalid_result = 0
    for row in rows:
        if not course_integrity(row):
            invalid_course += 1; continue
        if not opponent_integrity(row):
            invalid_opp += 1; continue
        if str(row.get("result_status") or "").lower() != "official" or str(row.get("race_status") or "").lower() != "official":
            pending += 1; continue
        actual = str(row.get("trifecta_ticket") or "").strip()
        if actual not in TICKET_INDEX:
            invalid_result += 1; continue
        base = [float(x) for x in row["base_probs"]]
        course = [float(x) for x in row["course_probs"]]
        pressure_delta = [float(row["adj_win"][i]) - float(row["base_win"][i]) for i in range(6)]
        opp = apply_first_place_delta(base, pressure_delta)
        combined = apply_first_place_delta(course, pressure_delta)
        records.append({
            "race_id": str(row["race_id"]), "race_date": row["race_date"],
            "venue_id": str(row.get("venue_id") or "").zfill(2),
            "BASE": metric(base, actual), "COURSE": metric(course, actual),
            "OPP": metric(opp, actual), "COMBINED": metric(combined, actual),
        })

    print(
        f"COURSE_OPP_COMBINED_COVERAGE=joined:{len(rows)} evaluated:{len(records)} pending:{pending} "
        f"invalid_course:{invalid_course} invalid_opp:{invalid_opp} invalid_result:{invalid_result}", flush=True,
    )
    base_m = aggregate(records, "BASE"); course_m = aggregate(records, "COURSE")
    opp_m = aggregate(records, "OPP"); combined_m = aggregate(records, "COMBINED")
    for name, vals in (("BASE", base_m), ("COURSE", course_m), ("OPP", opp_m), ("COMBINED", combined_m)):
        emit_model(name, vals, base_m)

    print(
        "COURSE_OPP_COMBINED_INCREMENTAL_VS_COURSE="
        f"ll:{combined_m[0]-course_m[0]:+.8f} brier:{combined_m[1]-course_m[1]:+.8f} rank:{combined_m[2]-course_m[2]:+.4f}", flush=True,
    )
    print(
        "COURSE_OPP_COMBINED_INCREMENTAL_VS_OPP="
        f"ll:{combined_m[0]-opp_m[0]:+.8f} brier:{combined_m[1]-opp_m[1]:+.8f} rank:{combined_m[2]-opp_m[2]:+.4f}", flush=True,
    )
    interaction = tuple(
        (combined_m[i]-base_m[i]) - (course_m[i]-base_m[i]) - (opp_m[i]-base_m[i])
        for i in range(3)
    )
    print(
        f"COURSE_OPP_COMBINED_INTERACTION=ll:{interaction[0]:+.8f} brier:{interaction[1]:+.8f} rank:{interaction[2]:+.4f}", flush=True,
    )
    for key, label in (("race_date", "DATE"), ("venue_id", "VENUE")):
        total, ll, br, rk, all3 = group_stability(records, key)
        print(
            f"COURSE_OPP_COMBINED_STABILITY={label} groups:{total} combined_better_vs_course_ll:{ll} "
            f"brier:{br} rank:{rk} all3:{all3}", flush=True,
        )

    cis = bootstrap_ci(records)
    for name, (mean, lo, hi) in zip(("LL", "BRIER", "RANK"), cis):
        print(
            f"COURSE_OPP_COMBINED_BOOTSTRAP={name} reps:{BOOT_REPS} seed:{BOOT_SEED} "
            f"mean_delta_combined_minus_course:{mean:+.8f} ci95:[{lo:+.8f},{hi:+.8f}]", flush=True,
        )
    deltas = [combined_m[i] - course_m[i] for i in range(3)]
    robust = bool(records) and all(x < 0.0 for x in deltas) and all(ci[2] < 0.0 for ci in cis)
    if robust:
        interpretation = "SUPPORTS_FIXED_COMBINED_FORWARD_RESEARCH_ONLY"
    elif records and any(x < 0.0 for x in deltas):
        interpretation = "MIXED_COMBINED_FORWARD_KEEP_COLLECTING"
    elif records:
        interpretation = "NO_INCREMENTAL_SUPPORT_OVER_COURSE"
    else:
        interpretation = "NO_COMMON_REALIZED_SAMPLE"
    print(f"COURSE_OPP_COMBINED_INTERPRETATION={interpretation}", flush=True)
    print("COURSE_OPP_COMBINED_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("COURSE_OPP_COMBINED_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"COURSE_OPP_COMBINED_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
