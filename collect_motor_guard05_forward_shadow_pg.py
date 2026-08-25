# -*- coding: utf-8 -*-
"""Frozen Forward collector for the GUARD05 young-motor candidate.

This is deliberately isolated from Production v24 and from the existing Motor2
candidate Shadow.  One row per race stores all 120 trifecta probabilities for:

- BASE: motor2 fixed at 33.0 for all lanes
- FULL: race-card actual motor2 for all lanes
- GUARD05: if that lane's motor had <=5 complete race-card appearances on dates
  strictly before TARGET_DATE within the verified official current generation,
  use 33.0 for that lane; otherwise use actual motor2.

The maturity definition is PRIOR_DAY. It is frozen before collection and cannot
use same-day results or same-day earlier races. Results and odds are never read.

Safety defaults:
- disabled unless MOTOR_GUARD_FORWARD_ENABLED=1
- dry-run unless MOTOR_GUARD_FORWARD_DRY_RUN=0
- write mode accepts only races whose deadline is still in the future
- first snapshot wins (`ON CONFLICT DO NOTHING`); later runs cannot rewrite it
- no Production decision, LINE, BUY/WATCH/SKIP, Railway setting, or coefficient
  is changed here.
"""
from __future__ import annotations

import copy
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import psycopg
from psycopg.rows import dict_row

import backtest_prob_motor_maturity_shrinkage_stability_pg as sh
import backtest_prob_motor_prior_appearance_maturity_pg as prior

JST = timezone(timedelta(hours=9))
VERSION_TEXT = "2026-08-25 motor-guard05-forward-shadow-v1"
MODEL_VERSION = 1
GUARD_MAX_PRIOR = 5
COUNT_MODE = "PRIOR_DAY"
TARGET_DATE = date.fromisoformat(os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d"))
ENABLED = (os.getenv("MOTOR_GUARD_FORWARD_ENABLED", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
DRY_RUN = (os.getenv("MOTOR_GUARD_FORWARD_DRY_RUN", "1") or "1").strip().lower() not in {"0", "false", "no", "off"}
ALLOW_PAST_DRY_RUN = (os.getenv("MOTOR_GUARD_FORWARD_ALLOW_PAST_DRY_RUN", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
MIN_LEAD_MINUTES = max(0, int(os.getenv("MOTOR_GUARD_FORWARD_MIN_LEAD_MINUTES", "3")))

TICKETS: Tuple[str, ...] = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7) if b != a
    for c in range(1, 7) if c not in (a, b)
)
if len(TICKETS) != 120:
    raise RuntimeError("ticket order must contain 120 trifectas")


def _sf(v: Any, d: float = 0.0) -> float:
    return prior.sf(v, d)


def _si(v: Any, d: int = 0) -> int:
    return prior.si(v, d)


def _card_valid(es: List[Dict[str, Any]]) -> bool:
    return (
        len(es) == 6
        and len({_si(e.get("lane")) for e in es}) == 6
        and all(_si(e.get("motor_no"), 0) > 0 for e in es)
        and all(0.0 <= _sf(e.get("motor_place2_rate"), -1.0) <= 100.0 for e in es)
    )


def _guard_probs(entries: List[Dict[str, Any]], venue: str, counts_by_lane: Dict[int, int]) -> Dict[str, float]:
    guarded = copy.deepcopy(entries)
    for e in guarded:
        lane = _si(e.get("lane"))
        if counts_by_lane.get(lane, 0) <= GUARD_MAX_PRIOR:
            e["motor_place2_rate"] = 33.0
    return sh.ticket_probs(guarded, venue, counts_by_lane, None)


def _load_rows(conn: psycopg.Connection[Any]):
    venues = sorted(prior.MOTOR_GENERATION_START)
    start_all = min(prior.MOTOR_GENERATION_START.values())
    with conn.cursor() as cur:
        cur.execute(
            """
            select r.race_id,r.race_date::date race_date,r.race_no::int race_no,
                   lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') venue,
                   r.deadline_at,
                   e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
                   e.local_place2_rate,e.avg_st,e.motor_no,e.motor_place2_rate
              from v2_races r
              join v2_race_entries e on e.race_id=r.race_id
             where r.race_date between %s and %s
               and lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0')=any(%s)
             order by r.race_date,venue,r.race_no,r.race_id,e.lane
            """,
            (start_all, TARGET_DATE, venues),
        )
        return [dict(x) for x in cur.fetchall()]


def _prepare(rows: List[Dict[str, Any]]):
    by_race: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    meta: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        rid = str(row.get("race_id") or "")
        if not rid:
            continue
        by_race[rid].append(row)
        meta[rid] = row

    counts: Dict[Tuple[str, str], int] = defaultdict(int)
    # PRIOR_DAY only: target-date cards never contribute to maturity counts.
    for rid, es0 in by_race.items():
        m = meta[rid]
        rd = m["race_date"]
        venue = str(m["venue"])
        if rd >= TARGET_DATE or rd < prior.MOTOR_GENERATION_START[venue]:
            continue
        es = sorted(es0, key=lambda x: _si(x.get("lane")))
        if not _card_valid(es):
            continue
        for e in es:
            counts[(venue, str(_si(e.get("motor_no"))))] += 1

    payloads: List[Dict[str, Any]] = []
    skipped = defaultdict(int)
    now = datetime.now(timezone.utc)
    min_deadline = now + timedelta(minutes=MIN_LEAD_MINUTES)

    for rid, es0 in sorted(by_race.items(), key=lambda kv: (meta[kv[0]]["race_date"], str(meta[kv[0]]["venue"]), _si(meta[kv[0]]["race_no"]), kv[0])):
        m = meta[rid]
        rd = m["race_date"]
        venue = str(m["venue"])
        if rd != TARGET_DATE:
            continue
        if rd < prior.MOTOR_GENERATION_START[venue]:
            skipped["pre_generation"] += 1
            continue
        es = sorted(es0, key=lambda x: _si(x.get("lane")))
        if not _card_valid(es):
            skipped["invalid_card"] += 1
            continue

        deadline = m.get("deadline_at")
        if not DRY_RUN or not ALLOW_PAST_DRY_RUN:
            if deadline is None:
                skipped["deadline_missing"] += 1
                continue
            if deadline <= min_deadline:
                skipped["not_forward"] += 1
                continue

        prior_by_lane = {
            _si(e["lane"]): counts[(venue, str(_si(e.get("motor_no"))))]
            for e in es
        }
        base = sh.ticket_probs(es, venue, prior_by_lane, -1)
        full = sh.ticket_probs(es, venue, prior_by_lane, None)
        guard = _guard_probs(es, venue, prior_by_lane)
        arrays = {
            "base_probs": [float(base[t]) for t in TICKETS],
            "full_probs": [float(full[t]) for t in TICKETS],
            "guard_probs": [float(guard[t]) for t in TICKETS],
        }
        for name, values in arrays.items():
            s = sum(values)
            if len(values) != 120 or abs(s - 1.0) > 1e-8:
                raise RuntimeError(f"invalid {name} race={rid} n={len(values)} sum={s}")

        by_lane = {_si(e["lane"]): e for e in es}
        counts_arr = [int(prior_by_lane[i]) for i in range(1, 7)]
        flags = [bool(prior_by_lane[i] <= GUARD_MAX_PRIOR) for i in range(1, 7)]
        payloads.append({
            "race_id": rid,
            "race_date": rd,
            "venue_id": venue,
            "race_no": _si(m.get("race_no")),
            "generation_start": prior.MOTOR_GENERATION_START[venue],
            "deadline_at": deadline,
            "motor_nos": [_si(by_lane[i].get("motor_no")) for i in range(1, 7)],
            "prior_day_counts": counts_arr,
            "actual_motor2": [float(_sf(by_lane[i].get("motor_place2_rate"), 33.0)) for i in range(1, 7)],
            "guard_flags": flags,
            **arrays,
        })
    return payloads, skipped


def _ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            create table if not exists v2_motor_guard05_forward_shadow (
              race_id text primary key,
              race_date date not null,
              venue_id text not null,
              race_no smallint not null,
              model_version smallint not null,
              count_mode text not null,
              guard_max_prior smallint not null,
              generation_start date not null,
              deadline_at timestamptz not null,
              snapshot_at timestamptz not null default now(),
              motor_nos smallint[] not null,
              prior_day_counts smallint[] not null,
              actual_motor2 real[] not null,
              guard_flags boolean[] not null,
              base_probs real[] not null,
              full_probs real[] not null,
              guard_probs real[] not null,
              created_at timestamptz not null default now(),
              updated_at timestamptz not null default now(),
              check (count_mode='PRIOR_DAY'),
              check (guard_max_prior=5),
              check (cardinality(motor_nos)=6),
              check (cardinality(prior_day_counts)=6),
              check (cardinality(actual_motor2)=6),
              check (cardinality(guard_flags)=6),
              check (cardinality(base_probs)=120),
              check (cardinality(full_probs)=120),
              check (cardinality(guard_probs)=120),
              check (snapshot_at < deadline_at)
            )
            """
        )
        cur.execute(
            "create index if not exists ix_motor_guard05_forward_date on v2_motor_guard05_forward_shadow(race_date)"
        )


def _insert(conn: psycopg.Connection[Any], payloads: List[Dict[str, Any]]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for p in payloads:
            cur.execute(
                """
                insert into v2_motor_guard05_forward_shadow(
                  race_id,race_date,venue_id,race_no,model_version,count_mode,
                  guard_max_prior,generation_start,deadline_at,motor_nos,
                  prior_day_counts,actual_motor2,guard_flags,base_probs,full_probs,guard_probs
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (race_id) do nothing
                """,
                (
                    p["race_id"],p["race_date"],p["venue_id"],p["race_no"],MODEL_VERSION,COUNT_MODE,
                    GUARD_MAX_PRIOR,p["generation_start"],p["deadline_at"],p["motor_nos"],
                    p["prior_day_counts"],p["actual_motor2"],p["guard_flags"],
                    p["base_probs"],p["full_probs"],p["guard_probs"],
                ),
            )
            inserted += max(0, cur.rowcount)
    return inserted


def main() -> None:
    print(f"MOTOR_GUARD_FORWARD_VERSION={VERSION_TEXT}", flush=True)
    print(f"MOTOR_GUARD_FORWARD_ENABLED={int(ENABLED)} DRY_RUN={int(DRY_RUN)} TARGET_DATE={TARGET_DATE}", flush=True)
    print(f"MOTOR_GUARD_FORWARD_POLICY=count_mode:{COUNT_MODE} guard_max_prior:{GUARD_MAX_PRIOR} min_lead_minutes:{MIN_LEAD_MINUTES} first_snapshot_wins", flush=True)
    print("MOTOR_GUARD_FORWARD_ISOLATION=shadow_only_no_results_no_odds_no_line_no_buy_no_prod_v24_change", flush=True)
    print("MOTOR_GUARD_FORWARD_TICKET_ORDER=lexicographic_lane_loop_120_fixed_v1", flush=True)
    if not ENABLED:
        print("MOTOR_GUARD_FORWARD_RESULT=SKIP_DISABLED", flush=True)
        return
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(url, row_factory=dict_row, autocommit=False) as conn:
        rows = _load_rows(conn)
        payloads, skipped = _prepare(rows)
        affected = sum(any(p["guard_flags"]) for p in payloads)
        guard_lanes = sum(sum(bool(x) for x in p["guard_flags"]) for p in payloads)
        print(
            "MOTOR_GUARD_FORWARD_PREVIEW="
            f"payloads:{len(payloads)} affected_races:{affected} guard_lanes:{guard_lanes} "
            f"invalid_card:{skipped['invalid_card']} pre_generation:{skipped['pre_generation']} "
            f"deadline_missing:{skipped['deadline_missing']} not_forward:{skipped['not_forward']}",
            flush=True,
        )
        if payloads:
            max_delta = max(
                max(abs(g - f) for g, f in zip(p["guard_probs"], p["full_probs"]))
                for p in payloads
            )
            print(f"MOTOR_GUARD_FORWARD_MAX_ABS_GUARD_FULL_PROB_DELTA={max_delta:.10f}", flush=True)
        if DRY_RUN:
            conn.rollback()
            print("MOTOR_GUARD_FORWARD_WRITE_ROWS=0", flush=True)
            print("MOTOR_GUARD_FORWARD_RESULT=PASS_DRY_RUN", flush=True)
            return

        _ensure_schema(conn)
        inserted = _insert(conn, payloads)
        conn.commit()
        print(f"MOTOR_GUARD_FORWARD_WRITE_ROWS={inserted}", flush=True)
        print("MOTOR_GUARD_FORWARD_RESULT=PASS_WRITE", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"MOTOR_GUARD_FORWARD_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True)
        raise
