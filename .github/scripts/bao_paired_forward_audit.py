# -*- coding: utf-8 -*-
"""Read-only forward audit for paired Bao early/late market snapshots.

Compares the frozen early de-vigged market distribution with the actionable late
market distribution.  It also applies the currently frozen robust research
coefficients for Motor2 (PR #108) and exhibition-time rank (PR #113, only when
a timestamp-safe realtime exhibition join is possible).

No DB writes, no Production decision changes, no LINE changes.
"""
from __future__ import annotations

import math
import os
import re
from collections import defaultdict

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

DB = os.getenv("DATABASE_URL", "").strip()
MOTOR_BETA = 0.06
EX_TIME_BETA = 0.06
MIN_FORWARD_PAIRS = 30
EPS = 1e-15
POS_W = (1.0, 0.6, 0.3)
CANONICAL_TICKETS = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7)
    if b != a
    for c in range(1, 7)
    if c not in (a, b)
)
assert len(CANONICAL_TICKETS) == 120


def nt(v):
    xs = re.findall(r"[1-6]", str(v or ""))
    return "-".join(xs[:3]) if len(xs) >= 3 else ""


def sf(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def zscore(vals):
    if len(vals) != 6:
        return None
    mu = sum(vals) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / 6.0)
    if sd < 1e-12:
        return None
    return {i + 1: (vals[i] - mu) / sd for i in range(6)}


def ticket_scores(z):
    out = {}
    for a in range(1, 7):
        for b in range(1, 7):
            if b == a:
                continue
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = (
                    POS_W[0] * z[a] + POS_W[1] * z[b] + POS_W[2] * z[c]
                )
    return out


def devig(odds_vec):
    if not odds_vec or len(odds_vec) != 120:
        return None
    vals = []
    for x in odds_vec:
        v = sf(x)
        if v is None or v <= 1.0:
            return None
        vals.append(1.0 / v)
    den = sum(vals)
    if den <= 0:
        return None
    return {t: vals[i] / den for i, t in enumerate(CANONICAL_TICKETS)}


def adjusted(q, score_maps, betas):
    vals = {}
    for t, p in q.items():
        expo = sum(beta * sc[t] for sc, beta in zip(score_maps, betas))
        vals[t] = p * math.exp(expo)
    den = sum(vals.values())
    return {t: v / den for t, v in vals.items()}


def cross_entropy(target, pred):
    return -sum(target[t] * math.log(max(pred[t], EPS)) for t in target)


def entropy(p):
    return -sum(v * math.log(max(v, EPS)) for v in p.values())


def l1(target, pred):
    return sum(abs(target[t] - pred[t]) for t in target)


def rank_of(p, ticket):
    if ticket not in p:
        return None
    pv = p[ticket]
    return 1 + sum(1 for v in p.values() if v > pv)


def top_ticket(p):
    return max(p, key=p.get)


def _table_columns(conn, table):
    with conn.cursor() as c:
        c.execute(
            """select column_name from information_schema.columns
               where table_schema='public' and table_name=%s""",
            (table,),
        )
        return {str(x["column_name"]) for x in c.fetchall()}


def _exhibition_time_scores(conn, race_id, late_at, columns):
    required = {"race_id", "lane", "exhibition_time_rank"}
    if not required.issubset(columns):
        return None, "required_columns_missing"
    ts_col = next(
        (x for x in ("captured_at", "snapshot_at", "collected_at", "created_at") if x in columns),
        None,
    )
    if not ts_col:
        return None, "timestamp_column_missing"

    q = sql.SQL(
        """select distinct on (lane) lane,exhibition_time_rank,{ts}
           from v2_realtime_exhibition_snapshots
           where race_id=%s and {ts} <= %s
           order by lane,{ts} desc"""
    ).format(ts=sql.Identifier(ts_col))
    with conn.cursor() as c:
        c.execute(q, (race_id, late_at))
        rows = [dict(x) for x in c.fetchall()]
    by = {int(x.get("lane") or 0): x for x in rows}
    if set(by) != {1, 2, 3, 4, 5, 6}:
        return None, "six_lanes_not_available_before_late"
    vals = []
    for lane in range(1, 7):
        r = sf(by[lane].get("exhibition_time_rank"))
        if r is None or int(r) not in range(1, 7):
            return None, "invalid_exhibition_rank"
        vals.append(-float(r))
    z = zscore(vals)
    return (ticket_scores(z), "ok") if z else (None, "zero_variance")


def main():
    if not DB:
        raise RuntimeError("DATABASE_URL is required")
    print("BAO_PAIR_AUDIT_MODE=read_only_forward", flush=True)
    print(
        f"BAO_PAIR_AUDIT_COEFFICIENTS=motor2:{MOTOR_BETA:.2f} exhibition_time:{EX_TIME_BETA:.2f}",
        flush=True,
    )
    print(f"BAO_PAIR_AUDIT_MIN_PAIRS={MIN_FORWARD_PAIRS}", flush=True)
    print("BAO_PAIR_AUDIT_POLICY=no_writes_no_production_no_line", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute(
                """select e.race_id,e.race_date,e.venue_id,e.race_no,
                          e.captured_at early_at,e.minutes_before early_mb,e.odds early_odds,
                          l.captured_at late_at,l.minutes_before late_mb,l.odds late_odds
                   from v2_bao_market_shadow_snapshots e
                   join v2_bao_market_shadow_snapshots l on l.race_id=e.race_id
                   where e.phase='early' and l.phase='late'
                   order by e.race_date,e.race_id"""
            )
            pairs = [dict(x) for x in c.fetchall()]

        race_ids = [str(x["race_id"]) for x in pairs]
        entries_by = defaultdict(list)
        results = {}
        if race_ids:
            with conn.cursor() as c:
                c.execute(
                    """select race_id,lane,motor_place2_rate from v2_race_entries
                       where race_id = any(%s) order by race_id,lane""",
                    (race_ids,),
                )
                for x in c.fetchall():
                    entries_by[str(x["race_id"])].append(dict(x))
                c.execute(
                    """select race_id,trifecta_ticket from v2_results
                       where race_id = any(%s)""",
                    (race_ids,),
                )
                results = {str(x["race_id"]): nt(x["trifecta_ticket"]) for x in c.fetchall()}

        ex_columns = _table_columns(conn, "v2_realtime_exhibition_snapshots")

        valid_market = motor_ready = exhibition_ready = result_ready = 0
        motor_improved = exhibition_improved = 0
        sum_motor_delta = sum_joint_delta = 0.0

        print(f"BAO_PAIR_AUDIT_PAIRED={len(pairs)}", flush=True)
        for row in pairs:
            rid = str(row["race_id"])
            qe = devig(row["early_odds"])
            ql = devig(row["late_odds"])
            if qe is None or ql is None:
                print(f"BAO_PAIR_AUDIT_SKIP=race:{rid} reason:invalid_120_vector", flush=True)
                continue
            valid_market += 1
            hlate = entropy(ql)
            ce_early = cross_entropy(ql, qe)
            kl_early = ce_early - hlate
            l1_early = l1(ql, qe)

            entries = entries_by.get(rid, [])
            by = {int(x.get("lane") or 0): x for x in entries}
            motor_score = None
            if set(by) == {1, 2, 3, 4, 5, 6}:
                vals = []
                for lane in range(1, 7):
                    v = sf(by[lane].get("motor_place2_rate"))
                    if v is None or not (0 <= v <= 100):
                        vals = []
                        break
                    vals.append(v)
                z = zscore(vals) if vals else None
                motor_score = ticket_scores(z) if z else None

            qm = None
            motor_delta = None
            if motor_score is not None:
                motor_ready += 1
                qm = adjusted(qe, [motor_score], [MOTOR_BETA])
                ce_motor = cross_entropy(ql, qm)
                motor_delta = ce_motor - ce_early
                sum_motor_delta += motor_delta
                motor_improved += int(motor_delta < 0)
                print(
                    f"BAO_PAIR_AUDIT_MOTOR=race:{rid} early_mb:{float(row['early_mb']):.2f} "
                    f"late_mb:{float(row['late_mb']):.2f} kl_early:{kl_early:.6f} "
                    f"ce_delta_motor:{motor_delta:.6f} l1_early:{l1_early:.6f} "
                    f"top_early:{top_ticket(qe)} top_motor:{top_ticket(qm)} top_late:{top_ticket(ql)}",
                    flush=True,
                )
            else:
                print(f"BAO_PAIR_AUDIT_MOTOR=race:{rid} status:not_ready", flush=True)

            ex_score, ex_reason = _exhibition_time_scores(
                conn, rid, row["late_at"], ex_columns
            )
            qj = None
            if motor_score is not None and ex_score is not None:
                exhibition_ready += 1
                qj = adjusted(qe, [motor_score, ex_score], [MOTOR_BETA, EX_TIME_BETA])
                base = cross_entropy(ql, qm)
                joint_delta = cross_entropy(ql, qj) - base
                sum_joint_delta += joint_delta
                exhibition_improved += int(joint_delta < 0)
                print(
                    f"BAO_PAIR_AUDIT_EXHIBITION=race:{rid} ce_delta_vs_motor:{joint_delta:.6f} "
                    f"top_joint:{top_ticket(qj)} status:timestamp_safe",
                    flush=True,
                )
            else:
                print(
                    f"BAO_PAIR_AUDIT_EXHIBITION=race:{rid} status:not_used reason:{ex_reason}",
                    flush=True,
                )

            actual = results.get(rid, "")
            if actual in qe:
                result_ready += 1
                parts = [
                    f"BAO_PAIR_AUDIT_RESULT_RACE=race:{rid}",
                    f"ticket:{actual}",
                    f"early_p:{qe[actual]:.8f}",
                    f"late_p:{ql[actual]:.8f}",
                    f"early_rank:{rank_of(qe, actual)}",
                    f"late_rank:{rank_of(ql, actual)}",
                ]
                if qm is not None:
                    parts += [f"motor_p:{qm[actual]:.8f}", f"motor_rank:{rank_of(qm, actual)}"]
                if qj is not None:
                    parts += [f"joint_p:{qj[actual]:.8f}", f"joint_rank:{rank_of(qj, actual)}"]
                print(" ".join(parts), flush=True)

    motor_avg = sum_motor_delta / motor_ready if motor_ready else 0.0
    joint_avg = sum_joint_delta / exhibition_ready if exhibition_ready else 0.0
    print(
        f"BAO_PAIR_AUDIT_COVERAGE=paired:{len(pairs)} valid_market:{valid_market} "
        f"motor_ready:{motor_ready} exhibition_ready:{exhibition_ready} result_ready:{result_ready}",
        flush=True,
    )
    print(
        f"BAO_PAIR_AUDIT_MOTOR_SUMMARY=improved:{motor_improved}/{motor_ready} avg_ce_delta:{motor_avg:.6f}",
        flush=True,
    )
    print(
        f"BAO_PAIR_AUDIT_EXHIBITION_SUMMARY=improved:{exhibition_improved}/{exhibition_ready} avg_ce_delta_vs_motor:{joint_avg:.6f}",
        flush=True,
    )
    verdict = "INSUFFICIENT_FORWARD_PAIRS" if valid_market < MIN_FORWARD_PAIRS else "READY_FOR_FORMAL_FORWARD_EVAL"
    print(f"BAO_PAIR_AUDIT_VERDICT={verdict}", flush=True)
    print("BAO_PAIR_AUDIT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
