# -*- coding: utf-8 -*-
"""Prospective timing-safe market-residual audit for frozen Bao features.

The coefficients were frozen before the forward sample:
- Motor2 beta = 0.06 (PR #108, final future split)
- exhibition-time beta = 0.06 (PR #113, selected in all four OOS splits)

For each dedicated exhibition Forward row, this audit selects the EARLIEST coherent
120-ticket realtime odds label whose first ticket was captured only AFTER the
exhibition snapshot and whose final ticket was captured before the race deadline.
This prevents combining newly-known exhibition evidence with stale earlier odds.

The market baseline is the de-vigged observed odds at that actionable timestamp.
The adjusted distribution is q * exp(0.06*Motor2 + 0.06*Exhibition).

Read-only research only. No DB writes, Production decision changes, LINE sends,
or purchase actions.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

DB = (os.getenv("DATABASE_URL") or "").strip()
OUTPUT = Path(os.getenv("VALUE_BAO_OUTPUT", "value-bao-post-exhibition-market-residual.json"))
MOTOR_BETA = 0.06
EXHIBITION_BETA = 0.06
MAX_LABEL_SPREAD_SECONDS = float(os.getenv("VALUE_BAO_MAX_LABEL_SPREAD_SECONDS", "60"))
MIN_FORWARD_RACES = 30
EPS = 1e-15
POS_W = (1.0, 0.6, 0.3)
LANES = {1, 2, 3, 4, 5, 6}
TICKETS = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7)
    if b != a
    for c in range(1, 7)
    if c not in (a, b)
)


def nt(v: Any) -> str:
    xs = re.findall(r"[1-6]", str(v or ""))
    return "-".join(xs[:3]) if len(xs) >= 3 else ""


def sf(v: Any) -> float | None:
    try:
        if v is None or v == "":
            return None
        x = float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def zscore(values: list[float]) -> dict[int, float] | None:
    if len(values) != 6:
        return None
    mu = sum(values) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in values) / 6.0)
    if sd < 1e-12:
        return None
    return {i + 1: (values[i] - mu) / sd for i in range(6)}


def ticket_scores(z: dict[int, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for a in range(1, 7):
        for b in range(1, 7):
            if b == a:
                continue
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = POS_W[0] * z[a] + POS_W[1] * z[b] + POS_W[2] * z[c]
    return out


def devig(odds_map: dict[str, Any]) -> dict[str, float] | None:
    if set(odds_map) != set(TICKETS):
        return None
    inv: dict[str, float] = {}
    for t in TICKETS:
        odd = sf(odds_map.get(t))
        if odd is None or odd <= 1.0:
            return None
        inv[t] = 1.0 / odd
    den = sum(inv.values())
    if den <= 0.0:
        return None
    return {t: x / den for t, x in inv.items()}


def adjusted(q: dict[str, float], motor: dict[str, float], exhibition: dict[str, float]) -> dict[str, float]:
    vals = {
        t: q[t] * math.exp(MOTOR_BETA * motor[t] + EXHIBITION_BETA * exhibition[t])
        for t in TICKETS
    }
    den = sum(vals.values())
    return {t: x / den for t, x in vals.items()}


def brier(p: dict[str, float], actual: str) -> float:
    return 1.0 - 2.0 * p[actual] + sum(x * x for x in p.values())


def rank_of(p: dict[str, float], actual: str) -> int:
    pa = p[actual]
    return 1 + sum(1 for t in TICKETS if p[t] > pa)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    w = pos - lo
    return xs[lo] * (1.0 - w) + xs[hi] * w


def load_market_rows(conn: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            with ex as (
              select race_id,race_date,venue_id,race_no,captured_at,deadline_at,
                     minutes_before,exhibition_time_ranks
                from v2_bao_exhibition_shadow_snapshots
            ), grouped as (
              select ex.race_id,o.snapshot_label,
                     count(*)::bigint as row_count,
                     count(distinct o.ticket)::bigint as ticket_count,
                     count(*) filter (where o.odds is not null and o.odds > 1.0)::bigint as positive_odds_count,
                     min(o.snapshot_at) as first_snapshot_at,
                     max(o.snapshot_at) as last_snapshot_at
                from ex
                join v2_realtime_odds_snapshots o on o.race_id=ex.race_id
               where o.snapshot_label is not null
               group by ex.race_id,ex.captured_at,ex.deadline_at,o.snapshot_label
              having count(*)=120
                 and count(distinct o.ticket)=120
                 and count(*) filter (where o.odds is not null and o.odds > 1.0)=120
                 and min(o.snapshot_at) >= ex.captured_at
                 and max(o.snapshot_at) <= ex.deadline_at
                 and extract(epoch from (max(o.snapshot_at)-min(o.snapshot_at))) <= %s
            ), chosen as (
              select distinct on (race_id)
                     race_id,snapshot_label,first_snapshot_at,last_snapshot_at
                from grouped
               order by race_id,first_snapshot_at asc,snapshot_label
            ), market as (
              select ch.race_id,ch.snapshot_label,ch.first_snapshot_at,ch.last_snapshot_at,
                     jsonb_object_agg(o.ticket,o.odds) as odds_map
                from chosen ch
                join v2_realtime_odds_snapshots o
                  on o.race_id=ch.race_id and o.snapshot_label=ch.snapshot_label
               group by ch.race_id,ch.snapshot_label,ch.first_snapshot_at,ch.last_snapshot_at
            )
            select ex.*,m.snapshot_label,m.first_snapshot_at,m.last_snapshot_at,m.odds_map,
                   r.result_status,r.race_status,r.trifecta_ticket
              from ex
              left join market m on m.race_id=ex.race_id
              left join v2_results r on r.race_id=ex.race_id
             order by ex.race_date,ex.venue_id,ex.race_no,ex.race_id
            """,
            (MAX_LABEL_SPREAD_SECONDS,),
        )
        return [dict(x) for x in cur.fetchall()]


def load_entries(conn: psycopg.Connection[Any], race_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not race_ids:
        return out
    with conn.cursor() as cur:
        cur.execute(
            """select race_id,lane,motor_place2_rate
                 from v2_race_entries
                where race_id = any(%s)
                order by race_id,lane""",
            (race_ids,),
        )
        for row in cur.fetchall():
            out[str(row["race_id"])].append(dict(row))
    return out


def feature_scores(row: dict[str, Any], entries: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, float]] | None:
    by = {int(x.get("lane") or 0): x for x in entries}
    if set(by) != LANES:
        return None
    motor_values: list[float] = []
    for lane in range(1, 7):
        x = sf(by[lane].get("motor_place2_rate"))
        if x is None or not (0.0 <= x <= 100.0):
            return None
        motor_values.append(x)

    ranks_raw = row.get("exhibition_time_ranks")
    if not isinstance(ranks_raw, list) or len(ranks_raw) != 6:
        return None
    try:
        ranks = [int(x) for x in ranks_raw]
    except Exception:
        return None
    if set(ranks) != LANES:
        return None

    zm = zscore(motor_values)
    zx = zscore([-float(x) for x in ranks])
    if zm is None or zx is None:
        return None
    return ticket_scores(zm), ticket_scores(zx)


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")

    print("VALUE_BAO_POSTEX_MODE=read_only_prospective_timing_safe", flush=True)
    print(f"VALUE_BAO_POSTEX_FIXED=motor2:{MOTOR_BETA:.2f} exhibition:{EXHIBITION_BETA:.2f}", flush=True)
    print("VALUE_BAO_POSTEX_ODDS_CONTRACT=first_complete_label_after_exhibition_before_deadline", flush=True)
    print(f"VALUE_BAO_POSTEX_MAX_LABEL_SPREAD_SECONDS={MAX_LABEL_SPREAD_SECONDS:g}", flush=True)
    print("VALUE_BAO_POSTEX_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='120s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local idle_in_transaction_session_timeout='30s'")
            cur.execute("set local max_parallel_workers_per_gather=0")
            cur.execute("set local work_mem='8MB'")
        rows = load_market_rows(conn)
        entries_by = load_entries(conn, [str(x["race_id"]) for x in rows])
        conn.rollback()

    coverage = Counter()
    labels: Counter[str] = Counter()
    lag_minutes: list[float] = []
    deadline_minutes: list[float] = []
    ll_market = ll_adj = br_market = br_adj = rank_market = rank_adj = 0.0
    deltas: list[float] = []
    by_date: dict[str, dict[str, float]] = defaultdict(lambda: {"n": 0, "delta_ll_sum": 0.0})

    coverage["exhibition_forward_rows"] = len(rows)
    for row in rows:
        if row.get("odds_map") is None:
            coverage["no_post_exhibition_complete_market"] += 1
            continue
        coverage["market_ready"] += 1
        if str(row.get("result_status") or "").lower() != "official" or str(row.get("race_status") or "").lower() != "official":
            coverage["pending_result"] += 1
            continue
        actual = nt(row.get("trifecta_ticket"))
        if actual not in TICKETS:
            coverage["invalid_result"] += 1
            continue
        q = devig(row["odds_map"])
        if q is None:
            coverage["invalid_market"] += 1
            continue
        scores = feature_scores(row, entries_by.get(str(row["race_id"]), []))
        if scores is None:
            coverage["invalid_features"] += 1
            continue
        motor, exhibition = scores
        a = adjusted(q, motor, exhibition)

        ml = -math.log(max(q[actual], EPS))
        al = -math.log(max(a[actual], EPS))
        mb = brier(q, actual)
        ab = brier(a, actual)
        mr = rank_of(q, actual)
        ar = rank_of(a, actual)
        d = al - ml

        coverage["evaluated"] += 1
        ll_market += ml
        ll_adj += al
        br_market += mb
        br_adj += ab
        rank_market += mr
        rank_adj += ar
        deltas.append(d)
        labels[str(row.get("snapshot_label") or "<none>")] += 1
        rd = str(row.get("race_date"))
        by_date[rd]["n"] += 1
        by_date[rd]["delta_ll_sum"] += d

        ex_at = row.get("captured_at")
        first_at = row.get("first_snapshot_at")
        last_at = row.get("last_snapshot_at")
        deadline = row.get("deadline_at")
        if all(isinstance(x, datetime) for x in (ex_at, first_at, last_at, deadline)):
            lag_minutes.append((first_at - ex_at).total_seconds() / 60.0)
            deadline_minutes.append((deadline - last_at).total_seconds() / 60.0)

    n = int(coverage["evaluated"])
    if n:
        mean_delta = sum(deltas) / n
        if n > 1:
            var = sum((x - mean_delta) ** 2 for x in deltas) / (n - 1)
            se = math.sqrt(var / n)
        else:
            se = 0.0
        metrics = {
            "n": n,
            "market_logloss": ll_market / n,
            "adjusted_logloss": ll_adj / n,
            "delta_logloss": mean_delta,
            "delta_logloss_se": se,
            "delta_logloss_z": mean_delta / se if se > 0 else None,
            "market_brier": br_market / n,
            "adjusted_brier": br_adj / n,
            "delta_brier": (br_adj - br_market) / n,
            "market_mean_rank": rank_market / n,
            "adjusted_mean_rank": rank_adj / n,
            "delta_mean_rank": (rank_adj - rank_market) / n,
        }
    else:
        metrics = {"n": 0}

    support = bool(
        n >= MIN_FORWARD_RACES
        and metrics.get("delta_logloss", 0.0) < 0.0
        and metrics.get("delta_brier", 0.0) <= 0.0
    )
    status = "SUPPORTS_FORMAL_VALUE_FOLLOWUP" if support else "MARKET_RESIDUAL_NOT_ESTABLISHED"

    date_rows = []
    for rd in sorted(by_date):
        x = by_date[rd]
        date_rows.append({
            "race_date": rd,
            "n": int(x["n"]),
            "delta_logloss": x["delta_ll_sum"] / x["n"] if x["n"] else None,
        })

    timing = {
        "exhibition_to_market_first_minutes": {
            "n": len(lag_minutes),
            "min": min(lag_minutes) if lag_minutes else None,
            "median": percentile(lag_minutes, 0.50),
            "p95": percentile(lag_minutes, 0.95),
            "max": max(lag_minutes) if lag_minutes else None,
        },
        "market_last_to_deadline_minutes": {
            "n": len(deadline_minutes),
            "min": min(deadline_minutes) if deadline_minutes else None,
            "median": percentile(deadline_minutes, 0.50),
            "p95": percentile(deadline_minutes, 0.95),
            "max": max(deadline_minutes) if deadline_minutes else None,
        },
    }

    summary = {
        "contract": "value_bao_post_exhibition_market_residual_v1",
        "coefficients_frozen_before_forward_sample": {"motor2": MOTOR_BETA, "exhibition_time": EXHIBITION_BETA},
        "market_contract": {
            "ticket_count": 120,
            "first_ticket_at_or_after_exhibition": True,
            "last_ticket_before_deadline": True,
            "max_label_spread_seconds": MAX_LABEL_SPREAD_SECONDS,
            "label_choice": "earliest_coherent_post_exhibition",
        },
        "coverage": dict(coverage),
        "snapshot_labels": dict(sorted(labels.items())),
        "timing": timing,
        "metrics": metrics,
        "by_date": date_rows,
        "status": status,
        "formal_profitability_established": False,
        "promotion_allowed": False,
        "mutation_performed": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"VALUE_BAO_POSTEX_COVERAGE={json.dumps(dict(coverage), sort_keys=True)}", flush=True)
    print(f"VALUE_BAO_POSTEX_LABELS={json.dumps(dict(sorted(labels.items())), sort_keys=True)}", flush=True)
    print(f"VALUE_BAO_POSTEX_TIMING={json.dumps(timing, sort_keys=True)}", flush=True)
    print(f"VALUE_BAO_POSTEX_METRICS={json.dumps(metrics, sort_keys=True)}", flush=True)
    print(f"VALUE_BAO_POSTEX_STATUS={status}", flush=True)
    print("VALUE_BAO_POSTEX_PROFITABILITY=NOT_ESTABLISHED_BY_THIS_AUDIT", flush=True)
    print("VALUE_BAO_POSTEX_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"VALUE_BAO_POSTEX_ERROR={type(exc).__name__}:{str(exc).replace(chr(10), ' ')[:700]}",
            flush=True,
        )
        raise
