# -*- coding: utf-8 -*-
"""Frozen Forward collector for the racer-by-course top3 current-v24 candidate.

Candidate frozen before this collector (PR #242):
- BASE = current Production PRE v24 probability formula with motor2/boat2 defaults
  33/34 and PROB_TEMP=2.20.
- COURSE = BASE lane raw strength + 0.50 * z(official course top3 rate).
- Early PRE proxy is lane == course.
- The coefficient 0.50 is frozen at the top of the pre-registered PR #242 grid;
  this collector must never search or expand that grid.

Forward safety:
- disabled unless RACER_COURSE_FORWARD_ENABLED=1
- dry-run unless RACER_COURSE_FORWARD_DRY_RUN=0
- exact-date official racer-course snapshots only
- all six course top3 values must exist and their current stored created_at must be
  on TARGET_DATE, <=08:15 JST, and before the race deadline
- normal writes require current TARGET_DATE and >=3 minutes lead
- collector reads race cards + racer-course snapshots only; no outcome/market data
- one row per race, ON CONFLICT DO NOTHING; first frozen probability snapshot wins
- Production v24 / FINAL / LINE / BUY-WATCH-SKIP are untouched
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Tuple

import psycopg
from psycopg.rows import dict_row

import v24_pre_candidate_notifier_pg as v24

JST = timezone(timedelta(hours=9))
VERSION = "2026-08-25 racer-course-top3-forward-shadow-v1"
MODEL_VERSION = 1
FORMULA_VERSION = "current_v24_plus_course_top3_z_raw_strength_v1"
TICKET_ORDER_VERSION = "lexicographic_lane_loop_120_fixed_v1"
FIXED_COEF = 0.50
SOURCE_CUTOFF = time(8, 15)
MIN_LEAD_MINUTES = 3.0
TARGET_DATE = date.fromisoformat(os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d"))
ENABLED = (os.getenv("RACER_COURSE_FORWARD_ENABLED", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
DRY_RUN = (os.getenv("RACER_COURSE_FORWARD_DRY_RUN", "1") or "1").strip().lower() not in {"0", "false", "no", "off"}
ALLOW_PAST_DRY_RUN = (os.getenv("RACER_COURSE_FORWARD_ALLOW_PAST_DRY_RUN", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}

TICKETS: Tuple[str, ...] = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7) if b != a
    for c in range(1, 7) if c not in (a, b)
)
if len(TICKETS) != 120:
    raise RuntimeError("ticket order must contain exactly 120 trifectas")


def _sf(v: Any, default: float | None = None) -> float | None:
    try:
        if v in (None, ""):
            return default
        x = float(v)
        return x if math.isfinite(x) else default
    except Exception:
        return default


def _si(v: Any, default: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else default
    except Exception:
        return default


def _aware_jst(v: Any) -> datetime | None:
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=JST)
    return v.astimezone(JST)


def _zs(vals: List[float]) -> List[float] | None:
    if len(vals) != 6:
        return None
    mu = sum(vals) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / 6.0)
    if sd < 1e-12:
        return None
    return [(x - mu) / sd for x in vals]


def _valid_entries(entries: List[Dict[str, Any]]) -> bool:
    return (
        len(entries) == 6
        and sorted(_si(e.get("lane")) for e in entries) == [1, 2, 3, 4, 5, 6]
        and all(1 <= _si(e.get("racer_class")) <= 4 for e in entries)
    )


def _clean_entries(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Preserve current Production PRE behavior: motor/boat rates are intentionally
    # absent so v24 uses its fixed defaults 33/34.
    return [
        {
            "lane": e.get("lane"),
            "racer_class": e.get("racer_class"),
            "national_win_rate": e.get("national_win_rate"),
            "national_place2_rate": e.get("national_place2_rate"),
            "local_place2_rate": e.get("local_place2_rate"),
            "avg_st": e.get("avg_st"),
        }
        for e in entries
    ]


def _distribution(entries: List[Dict[str, Any]], venue: str, coef: float) -> Dict[str, float]:
    by = v24._entry_by_lane(_clean_entries(entries))
    if sorted(by) != [1, 2, 3, 4, 5, 6]:
        raise RuntimeError("invalid six-lane entry card")

    vals: List[float] = []
    for lane in range(1, 7):
        row = next((e for e in entries if _si(e.get("lane")) == lane), None)
        x = _sf(row.get("course_top3_rate") if row else None)
        if x is None or not (0.0 <= x <= 100.0):
            raise RuntimeError("invalid six-lane course top3 values")
        vals.append(x)
    zs = _zs(vals)
    if zs is None:
        raise RuntimeError("degenerate six-lane course top3 values")

    raw = {
        lane: v24._lane_raw_strength(by[lane], lane, venue) + coef * zs[lane - 1]
        for lane in range(1, 7)
    }
    weights = {lane: math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)}
    total = sum(weights.values())
    if total <= 0:
        raise RuntimeError("invalid lane strength total")

    out: Dict[str, float] = {}
    for a in range(1, 7):
        pa = weights[a] / total
        rem_b = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / rem_b
            rem_c = rem_b - weights[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = pa * pb * (weights[c] / rem_c)
    z = sum(out.values())
    out = {ticket: p / z for ticket, p in out.items()}
    if len(out) != 120 or abs(sum(out.values()) - 1.0) > 1e-10:
        raise RuntimeError("invalid 120-ticket probability vector")
    return out


def _source_row_safe(row: Dict[str, Any], deadline: datetime) -> bool:
    created = _aware_jst(row.get("course_snapshot_created_at"))
    if created is None:
        return False
    if created.date() != TARGET_DATE:
        return False
    if created.time().replace(tzinfo=None) > SOURCE_CUTOFF:
        return False
    if created >= deadline:
        return False
    if str(row.get("course_source") or "") != "boatrace_official_racer_course":
        return False
    x = _sf(row.get("course_top3_rate"))
    return x is not None and 0.0 <= x <= 100.0


def _load(conn: psycopg.Connection[Any]) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select r.race_id,r.race_date::date race_date,r.race_no::int race_no,
                   lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') venue,
                   r.deadline_at,
                   e.lane,e.racer_number,e.racer_class,e.national_win_rate,
                   e.national_place2_rate,e.local_place2_rate,e.avg_st,
                   s.top3_rate course_top3_rate,s.created_at course_snapshot_created_at,
                   s.source course_source
              from v2_races r
              join v2_race_entries e on e.race_id=r.race_id
              left join v2_racer_course_stats_snapshots s
                on s.racer_number=e.racer_number
               and s.snapshot_date=r.race_date
               and s.course=e.lane
             where r.race_date=%s
             order by venue,r.race_no,r.race_id,e.lane
            """,
            (TARGET_DATE,),
        )
        return [dict(x) for x in cur.fetchall()]


def _prepare(rows: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    by_race: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rid = str(row.get("race_id") or "")
        if rid:
            by_race[rid].append(row)

    today = datetime.now(JST).date()
    now = datetime.now(JST)
    payloads: List[Dict[str, Any]] = []
    skipped: Dict[str, int] = defaultdict(int)

    for rid, raw_rows in sorted(by_race.items()):
        entries = sorted(raw_rows, key=lambda x: _si(x.get("lane")))
        if not _valid_entries(entries):
            skipped["invalid_card"] += 1
            continue
        deadline = _aware_jst(entries[0].get("deadline_at"))
        if deadline is None:
            skipped["deadline_missing"] += 1
            continue
        if not all(_source_row_safe(e, deadline) for e in entries):
            skipped["source_not_frozen_full6"] += 1
            continue

        if not (DRY_RUN and ALLOW_PAST_DRY_RUN):
            if TARGET_DATE != today:
                skipped["not_current_date"] += 1
                continue
            lead = (deadline - now).total_seconds() / 60.0
            if lead < MIN_LEAD_MINUTES:
                skipped["insufficient_lead"] += 1
                continue
            snapshot_at = datetime.now(JST)
        else:
            # PR/CI computation-only path. Never written and never called Forward evidence.
            latest_source = max(_aware_jst(e.get("course_snapshot_created_at")) for e in entries)
            snapshot_at = latest_source or deadline

        base = _distribution(entries, str(entries[0].get("venue") or "").zfill(2), 0.0)
        course = _distribution(entries, str(entries[0].get("venue") or "").zfill(2), FIXED_COEF)
        base_arr = [float(base[t]) for t in TICKETS]
        course_arr = [float(course[t]) for t in TICKETS]
        source_ats = [_aware_jst(e.get("course_snapshot_created_at")) for e in entries]
        rates = [float(_sf(e.get("course_top3_rate"), 0.0) or 0.0) for e in entries]
        payloads.append({
            "race_id": rid,
            "race_date": entries[0]["race_date"],
            "venue_id": str(entries[0].get("venue") or "").zfill(2),
            "race_no": _si(entries[0].get("race_no")),
            "deadline_at": deadline,
            "snapshot_at": snapshot_at,
            "minutes_before": (deadline - snapshot_at).total_seconds() / 60.0,
            "course_top3_rates": rates,
            "course_snapshot_ats": source_ats,
            "base_probs": base_arr,
            "course_probs": course_arr,
            "max_abs_delta": max(abs(a - b) for a, b in zip(base_arr, course_arr)),
        })
    return payloads, skipped


def _ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            create table if not exists v2_racer_course_top3_forward_shadow (
              race_id text primary key,
              race_date date not null,
              venue_id text not null,
              race_no smallint not null,
              model_version smallint not null,
              formula_version text not null,
              ticket_order_version text not null,
              course_coef numeric(7,4) not null,
              source_cutoff_jst text not null,
              deadline_at timestamptz not null,
              snapshot_at timestamptz not null,
              minutes_before real not null,
              course_top3_rates real[] not null,
              course_snapshot_ats timestamptz[] not null,
              base_probs real[] not null,
              course_probs real[] not null,
              created_at timestamptz not null default now(),
              check (model_version=1),
              check (course_coef=0.5000),
              check (source_cutoff_jst='08:15'),
              check (ticket_order_version='lexicographic_lane_loop_120_fixed_v1'),
              check (cardinality(course_top3_rates)=6),
              check (cardinality(course_snapshot_ats)=6),
              check (cardinality(base_probs)=120),
              check (cardinality(course_probs)=120),
              check (snapshot_at < deadline_at),
              check (minutes_before >= 3.0)
            )
            """
        )
        cur.execute(
            "create index if not exists ix_racer_course_top3_forward_date on v2_racer_course_top3_forward_shadow(race_date)"
        )


def _insert(conn: psycopg.Connection[Any], payloads: List[Dict[str, Any]]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for p in payloads:
            cur.execute(
                """
                insert into v2_racer_course_top3_forward_shadow(
                  race_id,race_date,venue_id,race_no,model_version,formula_version,
                  ticket_order_version,course_coef,source_cutoff_jst,deadline_at,
                  snapshot_at,minutes_before,course_top3_rates,course_snapshot_ats,
                  base_probs,course_probs
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (race_id) do nothing
                """,
                (
                    p["race_id"],p["race_date"],p["venue_id"],p["race_no"],MODEL_VERSION,
                    FORMULA_VERSION,TICKET_ORDER_VERSION,FIXED_COEF,"08:15",
                    p["deadline_at"],p["snapshot_at"],p["minutes_before"],
                    p["course_top3_rates"],p["course_snapshot_ats"],p["base_probs"],p["course_probs"],
                ),
            )
            inserted += max(0, cur.rowcount)
    return inserted


def main() -> None:
    print(f"RACER_COURSE_FORWARD_VERSION={VERSION}", flush=True)
    print(f"RACER_COURSE_FORWARD_TARGET_DATE={TARGET_DATE}", flush=True)
    print(f"RACER_COURSE_FORWARD_ENABLED={int(ENABLED)} DRY_RUN={int(DRY_RUN)}", flush=True)
    print(
        "RACER_COURSE_FORWARD_POLICY=coef:0.50 source_cutoff:08:15_jst lane_as_course first_snapshot_wins min_lead_minutes:3",
        flush=True,
    )
    print("RACER_COURSE_FORWARD_ISOLATION=shadow_only_no_outcome_no_market_no_line_no_buy_no_prod_v24_change", flush=True)
    print(f"RACER_COURSE_FORWARD_TICKET_ORDER={TICKET_ORDER_VERSION}", flush=True)

    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL required")
    if not ENABLED:
        print("RACER_COURSE_FORWARD_RESULT=SKIP_DISABLED", flush=True)
        return
    if not DRY_RUN and TARGET_DATE != datetime.now(JST).date():
        raise RuntimeError("confirmed write requires current TARGET_DATE")

    with psycopg.connect(url, row_factory=dict_row, autocommit=False) as conn:
        rows = _load(conn)
        payloads, skipped = _prepare(rows)
        print(
            "RACER_COURSE_FORWARD_PREVIEW="
            f"target_entry_rows:{len(rows)} payloads:{len(payloads)} "
            + " ".join(f"{k}:{v}" for k, v in sorted(skipped.items())),
            flush=True,
        )
        if payloads:
            deltas = [float(p["max_abs_delta"]) for p in payloads]
            print(
                f"RACER_COURSE_FORWARD_DELTA=max_abs_min:{min(deltas):.8f} max_abs_avg:{sum(deltas)/len(deltas):.8f} max_abs_max:{max(deltas):.8f}",
                flush=True,
            )
        if DRY_RUN:
            conn.rollback()
            print("RACER_COURSE_FORWARD_WRITE_ROWS=0", flush=True)
            print("RACER_COURSE_FORWARD_RESULT=PASS_DRY_RUN", flush=True)
            return

        _ensure_schema(conn)
        inserted = _insert(conn, payloads)
        conn.commit()
        print(f"RACER_COURSE_FORWARD_WRITE_ROWS={inserted}", flush=True)
        print("RACER_COURSE_FORWARD_RESULT=PASS_WRITE", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"RACER_COURSE_FORWARD_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True)
        raise
