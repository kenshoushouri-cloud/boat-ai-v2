# -*- coding: utf-8 -*-
"""Frozen Forward collector for the fixed exhibition-ST v24 candidate.

Research candidate frozen before this collector:
- BASE = current v24 PRE probability formula, motor2/boat2 defaults 33/34,
  PROB_TEMP=2.20.
- ST = BASE multiplied by the PR #122 ticket score with beta=-0.02 exactly.
- ST score = z(-start_timing_rank) with ticket position weights 1.0/0.6/0.3.

Forward safety:
- disabled unless EXH_ST_FORWARD_ENABLED=1
- dry-run unless EXH_ST_FORWARD_DRY_RUN=0
- normal write path fetches BOAT RACE official beforeinfo only 8-15 minutes before deadline
- collector never reads results or odds
- one row per race, `ON CONFLICT DO NOTHING`; first snapshot wins forever
- Production v24 / FINAL / LINE / BUY-WATCH-SKIP are untouched

PR CI may use stored historical exhibition ranks only when BOTH dry-run and
EXH_ST_FORWARD_ALLOW_PAST_DRY_RUN=1. That path exists solely to exercise the
fixed probability machinery without any database write; confirmed writes always
use fresh official beforeinfo.
"""
from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Tuple

import psycopg
from psycopg.rows import dict_row

import v21_realtime_collector_pg as rt
import v24_pre_candidate_notifier_pg as v24

JST = rt.JST
VERSION_TEXT = "2026-08-25 exhibition-st-forward-shadow-v1"
MODEL_VERSION = 1
FIXED_ST_BETA = -0.02
WINDOW_LO_MIN = 8.0
WINDOW_HI_MIN = 15.0
POS = (1.0, 0.6, 0.3)
EPS = 1e-15
TARGET_DATE = date.fromisoformat(os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d"))
ENABLED = (os.getenv("EXH_ST_FORWARD_ENABLED", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
DRY_RUN = (os.getenv("EXH_ST_FORWARD_DRY_RUN", "1") or "1").strip().lower() not in {"0", "false", "no", "off"}
ALLOW_PAST_DRY_RUN = (os.getenv("EXH_ST_FORWARD_ALLOW_PAST_DRY_RUN", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}
DRYRUN_STORED_HISTORICAL = (os.getenv("EXH_ST_FORWARD_DRYRUN_STORED_HISTORICAL", "0") or "0").strip().lower() in {"1", "true", "yes", "on"}

TICKETS: Tuple[str, ...] = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7) if b != a
    for c in range(1, 7) if c not in (a, b)
)
if len(TICKETS) != 120:
    raise RuntimeError("ticket order must contain exactly 120 trifectas")


def _sf(v: Any, d: float = 0.0) -> float:
    try:
        return float(v) if v not in (None, "") else d
    except Exception:
        return d


def _si(v: Any, d: int = 0) -> int:
    try:
        return int(float(v)) if v not in (None, "") else d
    except Exception:
        return d


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
        and all(1 <= _si(e.get("racer_class"), 0) <= 4 for e in entries)
    )


def _base_distribution(entries: List[Dict[str, Any]], venue: str) -> Dict[str, float]:
    # Match current Production PRE fetch: motor_place2_rate and boat_place2_rate are
    # intentionally absent, so _lane_raw_strength uses its fixed 33/34 defaults.
    clean = [
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
    by = v24._entry_by_lane(clean)
    if sorted(by) != [1, 2, 3, 4, 5, 6]:
        raise RuntimeError("invalid six-lane entry card")
    raw = {lane: v24._lane_raw_strength(by[lane], lane, venue) for lane in range(1, 7)}
    w = {lane: math.exp(raw[lane] / v24.PROB_TEMP) for lane in range(1, 7)}
    total = sum(w.values())
    out: Dict[str, float] = {}
    for a in range(1, 7):
        pa = w[a] / total
        rem_b = total - w[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = w[b] / rem_b
            rem_c = rem_b - w[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = pa * pb * (w[c] / rem_c)
    z = sum(out.values())
    out = {t: p / z for t, p in out.items()}
    if len(out) != 120 or abs(sum(out.values()) - 1.0) > 1e-10:
        raise RuntimeError("invalid base 120 probability vector")
    return out


def _st_score(ranks: List[int]) -> Dict[str, float]:
    if len(ranks) != 6 or sorted(ranks) != [1, 2, 3, 4, 5, 6]:
        raise RuntimeError(f"invalid start-timing ranks: {ranks}")
    # Exact PR #122 orientation. Do not reinterpret the sign here.
    zs = _zs([-float(rank) for rank in ranks])
    if zs is None:
        raise RuntimeError("degenerate start-timing ranks")
    out: Dict[str, float] = {}
    for a in range(1, 7):
        for b in range(1, 7):
            if b == a:
                continue
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = POS[0] * zs[a - 1] + POS[1] * zs[b - 1] + POS[2] * zs[c - 1]
    return out


def _st_distribution(base: Dict[str, float], ranks: List[int]) -> Dict[str, float]:
    score = _st_score(ranks)
    vals = {t: base[t] * math.exp(FIXED_ST_BETA * score[t]) for t in TICKETS}
    z = sum(vals.values())
    out = {t: vals[t] / z for t in TICKETS}
    if len(out) != 120 or abs(sum(out.values()) - 1.0) > 1e-10:
        raise RuntimeError("invalid ST-adjusted 120 probability vector")
    return out


def _official_start_ranks(target_date: date, venue: str, race_no: int) -> tuple[List[int] | None, datetime]:
    html = rt._fetch(rt._official_url("beforeinfo", target_date.isoformat(), venue, race_no))
    captured = datetime.now(JST)
    if not html or rt._looks_no_data(html):
        return None, captured
    rows = rt.parse_exhibition(html)
    by = {_si(row.get("lane")): row for row in rows if 1 <= _si(row.get("lane")) <= 6}
    if sorted(by) != [1, 2, 3, 4, 5, 6]:
        return None, captured
    ranks = [_si(by[lane].get("start_timing_rank"), 0) for lane in range(1, 7)]
    if sorted(ranks) != [1, 2, 3, 4, 5, 6]:
        return None, captured
    return ranks, captured


def _load_target_rows(conn: psycopg.Connection[Any]) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select r.race_id,r.race_date::date race_date,r.race_no::int race_no,
                   lpad(coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,'')),2,'0') venue,
                   r.deadline_at,
                   e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
                   e.local_place2_rate,e.avg_st
              from v2_races r
              join v2_race_entries e on e.race_id=r.race_id
             where r.race_date=%s
             order by venue,r.race_no,r.race_id,e.lane
            """,
            (TARGET_DATE,),
        )
        return [dict(x) for x in cur.fetchall()]


def _load_stored_historical_ranks(conn: psycopg.Connection[Any], race_ids: List[str]) -> Dict[str, List[int]]:
    if not (DRY_RUN and ALLOW_PAST_DRY_RUN and DRYRUN_STORED_HISTORICAL):
        return {}
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,lane,start_timing_rank
              from v2_realtime_exhibition_snapshots
             where race_id=any(%s) and snapshot_label='historical'
             order by race_id,lane
            """,
            (race_ids,),
        )
        rows = [dict(x) for x in cur.fetchall()]
    by: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by[str(row["race_id"])].append(row)
    out: Dict[str, List[int]] = {}
    for rid, rr in by.items():
        rr = sorted(rr, key=lambda x: _si(x.get("lane")))
        ranks = [_si(x.get("start_timing_rank"), 0) for x in rr]
        if len(rr) == 6 and sorted(_si(x.get("lane")) for x in rr) == [1, 2, 3, 4, 5, 6] and sorted(ranks) == [1, 2, 3, 4, 5, 6]:
            out[rid] = ranks
    return out


def _prepare(conn: psycopg.Connection[Any], rows: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    by_race: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    meta: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        rid = str(row.get("race_id") or "")
        if rid:
            by_race[rid].append(row)
            meta[rid] = row
    stored = _load_stored_historical_ranks(conn, list(by_race))
    payloads: List[Dict[str, Any]] = []
    skipped: Dict[str, int] = defaultdict(int)
    now = datetime.now(JST)

    for rid, es0 in sorted(by_race.items(), key=lambda kv: (str(meta[kv[0]]["venue"]), _si(meta[kv[0]]["race_no"]), kv[0])):
        m = meta[rid]
        es = sorted(es0, key=lambda x: _si(x.get("lane")))
        if not _valid_entries(es):
            skipped["invalid_card"] += 1
            continue
        deadline = m.get("deadline_at")
        if deadline is None:
            skipped["deadline_missing"] += 1
            continue
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=JST)
        deadline = deadline.astimezone(JST)

        if DRY_RUN and ALLOW_PAST_DRY_RUN:
            # Deterministic CI path. No write and no claim of Forward evidence.
            ranks = stored.get(rid)
            captured = deadline
            source = "stored_historical_dryrun_only"
            if ranks is None:
                skipped["st_missing"] += 1
                continue
        else:
            minutes_before_now = (deadline - now).total_seconds() / 60.0
            if not (WINDOW_LO_MIN <= minutes_before_now <= WINDOW_HI_MIN):
                skipped["outside_window"] += 1
                continue
            ranks, captured = _official_start_ranks(TARGET_DATE, str(m["venue"]), _si(m["race_no"]))
            source = "official_beforeinfo"
            if ranks is None:
                skipped["st_missing"] += 1
                continue
            minutes_before_captured = (deadline - captured).total_seconds() / 60.0
            if not (WINDOW_LO_MIN <= minutes_before_captured <= WINDOW_HI_MIN):
                skipped["window_drift"] += 1
                continue

        base = _base_distribution(es, str(m["venue"]))
        st = _st_distribution(base, ranks)
        base_arr = [float(base[t]) for t in TICKETS]
        st_arr = [float(st[t]) for t in TICKETS]
        max_delta = max(abs(a - b) for a, b in zip(base_arr, st_arr))
        payloads.append({
            "race_id": rid,
            "race_date": m["race_date"],
            "venue_id": str(m["venue"]),
            "race_no": _si(m["race_no"]),
            "deadline_at": deadline,
            "snapshot_at": captured,
            "minutes_before": (deadline - captured).total_seconds() / 60.0,
            "start_timing_ranks": ranks,
            "base_probs": base_arr,
            "st_probs": st_arr,
            "max_abs_delta": max_delta,
            "source": source,
        })
    return payloads, skipped


def _ensure_schema(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            create table if not exists v2_exhibition_st_forward_shadow (
              race_id text primary key,
              race_date date not null,
              venue_id text not null,
              race_no smallint not null,
              model_version smallint not null,
              formula_version text not null,
              ticket_order_version text not null,
              st_beta numeric(7,4) not null,
              deadline_at timestamptz not null,
              snapshot_at timestamptz not null,
              minutes_before real not null,
              start_timing_ranks smallint[] not null,
              base_probs real[] not null,
              st_probs real[] not null,
              source text not null,
              created_at timestamptz not null default now(),
              check (st_beta=-0.0200),
              check (ticket_order_version='lexicographic_lane_loop_120_fixed_v1'),
              check (cardinality(start_timing_ranks)=6),
              check (cardinality(base_probs)=120),
              check (cardinality(st_probs)=120),
              check (snapshot_at < deadline_at),
              check (minutes_before >= 8.0 and minutes_before <= 15.0)
            )
            """
        )
        cur.execute(
            "create index if not exists ix_exhibition_st_forward_date on v2_exhibition_st_forward_shadow(race_date)"
        )


def _insert(conn: psycopg.Connection[Any], payloads: List[Dict[str, Any]]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for p in payloads:
            cur.execute(
                """
                insert into v2_exhibition_st_forward_shadow(
                  race_id,race_date,venue_id,race_no,model_version,formula_version,
                  ticket_order_version,st_beta,deadline_at,snapshot_at,minutes_before,
                  start_timing_ranks,base_probs,st_probs,source
                ) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (race_id) do nothing
                """,
                (
                    p["race_id"],p["race_date"],p["venue_id"],p["race_no"],MODEL_VERSION,
                    "current_v24_fixed33_34_temp2.20_plus_exhibition_st_beta_-0.02_v1",
                    "lexicographic_lane_loop_120_fixed_v1",FIXED_ST_BETA,p["deadline_at"],
                    p["snapshot_at"],p["minutes_before"],p["start_timing_ranks"],
                    p["base_probs"],p["st_probs"],p["source"],
                ),
            )
            inserted += max(0, cur.rowcount)
    return inserted


def main() -> None:
    print(f"EXH_ST_FORWARD_VERSION={VERSION_TEXT}", flush=True)
    print(f"EXH_ST_FORWARD_ENABLED={int(ENABLED)} DRY_RUN={int(DRY_RUN)} TARGET_DATE={TARGET_DATE}", flush=True)
    print(f"EXH_ST_FORWARD_MODEL=base:current_v24_fixed33_34_temp2.20 st_beta:{FIXED_ST_BETA:+.2f}_fixed_pr122_first_train", flush=True)
    print(f"EXH_ST_FORWARD_WINDOW={WINDOW_LO_MIN:.1f}-{WINDOW_HI_MIN:.1f}_minutes_before_deadline", flush=True)
    print("EXH_ST_FORWARD_TICKET_ORDER=lexicographic_lane_loop_120_fixed_v1", flush=True)
    print("EXH_ST_FORWARD_ISOLATION=shadow_only_no_results_no_odds_no_line_no_buy_no_prod_v24_change_first_snapshot_wins", flush=True)
    if not ENABLED:
        print("EXH_ST_FORWARD_RESULT=SKIP_DISABLED", flush=True)
        return
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL required")

    with psycopg.connect(url, row_factory=dict_row, autocommit=False) as conn:
        rows = _load_target_rows(conn)
        payloads, skipped = _prepare(conn, rows)
        max_delta = max((p["max_abs_delta"] for p in payloads), default=0.0)
        source_counts: Dict[str, int] = defaultdict(int)
        for p in payloads:
            source_counts[p["source"]] += 1
        print(
            "EXH_ST_FORWARD_PREVIEW="
            f"payloads:{len(payloads)} invalid_card:{skipped['invalid_card']} "
            f"deadline_missing:{skipped['deadline_missing']} outside_window:{skipped['outside_window']} "
            f"st_missing:{skipped['st_missing']} window_drift:{skipped['window_drift']} "
            f"max_abs_prob_delta:{max_delta:.10f}",
            flush=True,
        )
        print(
            "EXH_ST_FORWARD_SOURCE_COUNTS=" + ",".join(f"{k}:{v}" for k, v in sorted(source_counts.items())),
            flush=True,
        )
        if DRY_RUN:
            conn.rollback()
            print("EXH_ST_FORWARD_WRITE_ROWS=0", flush=True)
            print("EXH_ST_FORWARD_RESULT=PASS_DRY_RUN", flush=True)
            return

        # Confirmed writes may NEVER use the historical dry-run source.
        if any(p["source"] != "official_beforeinfo" for p in payloads):
            raise RuntimeError("write payload contains non-forward source")
        _ensure_schema(conn)
        inserted = _insert(conn, payloads)
        conn.commit()
        print(f"EXH_ST_FORWARD_WRITE_ROWS={inserted}", flush=True)
        print("EXH_ST_FORWARD_RESULT=PASS_WRITE", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"EXH_ST_FORWARD_ERROR={type(exc).__name__}:{str(exc).replace(chr(10),' ')[:700]}", flush=True)
        raise
