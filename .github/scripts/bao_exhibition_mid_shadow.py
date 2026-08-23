# -*- coding: utf-8 -*-
"""Isolated compact Bao exhibition-time Shadow collector.

The market early snapshot is intentionally 20-30 minutes before deadline, when
official exhibition data is often not available yet. This collector therefore
freezes exhibition evidence separately in a non-overlapping pre-late window.

Writes ONLY v2_bao_exhibition_shadow_snapshots. Production decisions, market
Shadow rows, realtime snapshot tables, and LINE are never changed.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row

import v21_realtime_collector_pg as rt

JST = timezone(timedelta(hours=9))
DB = os.getenv("DATABASE_URL", "").strip()
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
WINDOW_LO = float(os.getenv("BAO_EXSHADOW_MIN_LO", "8"))
WINDOW_HI = float(os.getenv("BAO_EXSHADOW_MIN_HI", "15"))
LANES = {1, 2, 3, 4, 5, 6}

DDL = """
create table if not exists v2_bao_exhibition_shadow_snapshots (
 race_id text primary key,
 race_date date not null,
 venue_id text not null,
 race_no smallint not null,
 captured_at timestamptz not null,
 deadline_at timestamptz not null,
 minutes_before real not null,
 exhibition_times real[] not null,
 exhibition_time_ranks smallint[] not null,
 source text not null default 'official_beforeinfo',
 schema_version smallint not null default 1,
 created_at timestamptz not null default now(),
 check (cardinality(exhibition_times)=6),
 check (cardinality(exhibition_time_ranks)=6)
)
"""


def in_window(minutes_before: float) -> bool:
    return WINDOW_LO <= minutes_before <= WINDOW_HI


def parse_complete(html: str | None):
    if not html or rt._looks_no_data(html):
        return None
    rows = rt.parse_exhibition(html)
    by = {}
    for row in rows:
        lane = rt._safe_int(row.get("lane"), 0)
        if lane in LANES:
            by[lane] = row
    if set(by) != LANES:
        return None
    times = []
    ranks = []
    for lane in range(1, 7):
        t = rt._safe_float(by[lane].get("exhibition_time"), 0.0)
        rank = rt._safe_int(by[lane].get("exhibition_time_rank"), 0)
        if t <= 0 or rank not in LANES:
            return None
        times.append(float(t))
        ranks.append(int(rank))
    if set(ranks) != LANES:
        return None
    return times, ranks


def has_early_market(conn, race_id: str) -> bool:
    with conn.cursor() as c:
        c.execute(
            "select to_regclass('public.v2_bao_market_shadow_snapshots') tbl"
        )
        if not c.fetchone()["tbl"]:
            return False
        c.execute(
            "select 1 ok from v2_bao_market_shadow_snapshots "
            "where race_id=%s and phase='early'",
            (race_id,),
        )
        return c.fetchone() is not None


def main():
    if not DB:
        raise RuntimeError("DATABASE_URL is required")
    now = datetime.now(JST)
    print(
        f"BAO_EXSHADOW_MODE=isolated_compact_write target:{TARGET_DATE} now:{now.isoformat()}",
        flush=True,
    )
    print(f"BAO_EXSHADOW_WINDOW={WINDOW_LO:.1f}-{WINDOW_HI:.1f}", flush=True)
    print("BAO_EXSHADOW_SCHEMA=one_row_per_race_real6_rank6", flush=True)
    print("BAO_EXSHADOW_SOURCE=official_beforeinfo", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as c:
            c.execute(DDL)
            c.execute(
                "create index if not exists ix_v2_bao_exhibition_shadow_time "
                "on v2_bao_exhibition_shadow_snapshots(captured_at)"
            )
            c.execute(
                """select race_id,race_date,coalesce(venue_id,venue_code) venue_id,
                          race_no,deadline_at
                   from v2_races
                   where race_date=%s and deadline_at is not null
                   order by deadline_at""",
                (TARGET_DATE,),
            )
            races = [dict(x) for x in c.fetchall()]

        targets = []
        for r in races:
            deadline = r["deadline_at"]
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=JST)
            deadline = deadline.astimezone(JST)
            mb = (deadline - now).total_seconds() / 60.0
            if in_window(mb):
                targets.append((r, deadline, mb))

        print(f"BAO_EXSHADOW_TARGETS={len(targets)}", flush=True)
        saved = 0
        missing = 0
        drift = 0
        existing = 0
        unpairable = 0

        for r, deadline, _ in targets:
            rid = str(r["race_id"])
            venue = str(r.get("venue_id") or "").zfill(2)
            rno = int(r.get("race_no") or 0)
            with conn.cursor() as c:
                c.execute(
                    "select 1 ok from v2_bao_exhibition_shadow_snapshots where race_id=%s",
                    (rid,),
                )
                if c.fetchone():
                    existing += 1
                    continue

            if not has_early_market(conn, rid):
                unpairable += 1
                print(
                    f"BAO_EXSHADOW_SKIP race:{rid} reason:early_missing_unpairable",
                    flush=True,
                )
                continue

            html = rt._fetch(rt._official_url("beforeinfo", TARGET_DATE, venue, rno))
            captured = datetime.now(JST)
            mb2 = (deadline - captured).total_seconds() / 60.0
            if not in_window(mb2):
                drift += 1
                print(
                    f"BAO_EXSHADOW_SKIP race:{rid} reason:window_drift minutes_before:{mb2:.2f}",
                    flush=True,
                )
                continue
            parsed = parse_complete(html)
            if parsed is None:
                missing += 1
                print(
                    f"BAO_EXSHADOW_SKIP race:{rid} reason:incomplete_official_beforeinfo "
                    f"minutes_before:{mb2:.2f}",
                    flush=True,
                )
                continue
            times, ranks = parsed
            with conn.cursor() as c:
                c.execute(
                    """insert into v2_bao_exhibition_shadow_snapshots
                       (race_id,race_date,venue_id,race_no,captured_at,deadline_at,
                        minutes_before,exhibition_times,exhibition_time_ranks)
                       values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       on conflict (race_id) do nothing""",
                    (
                        rid,
                        r["race_date"],
                        venue,
                        rno,
                        captured,
                        deadline,
                        round(mb2, 3),
                        times,
                        ranks,
                    ),
                )
                wrote = c.rowcount
            if wrote:
                saved += 1
                print(
                    f"BAO_EXSHADOW_SAVE race:{rid} minutes_before:{mb2:.2f} "
                    "lanes:6 time_n:6 rank_n:6",
                    flush=True,
                )
            else:
                existing += 1

        with conn.cursor() as c:
            c.execute(
                """select count(*) rows,count(distinct race_id) races,
                          min(captured_at) first_at,max(captured_at) last_at,
                          min(cardinality(exhibition_times)) min_time_n,
                          max(cardinality(exhibition_times)) max_time_n,
                          min(cardinality(exhibition_time_ranks)) min_rank_n,
                          max(cardinality(exhibition_time_ranks)) max_rank_n
                   from v2_bao_exhibition_shadow_snapshots"""
            )
            x = dict(c.fetchone())
            print(
                "BAO_EXSHADOW_TOTAL rows:{rows} races:{races} time_n:{min_time_n}-{max_time_n} "
                "rank_n:{min_rank_n}-{max_rank_n} first:{first_at} last:{last_at}".format(**x),
                flush=True,
            )
            c.execute(
                "select pg_total_relation_size('v2_bao_exhibition_shadow_snapshots')::bigint bytes"
            )
            print(f"BAO_EXSHADOW_TABLE_BYTES={c.fetchone()['bytes']}", flush=True)

    print(
        f"BAO_EXSHADOW_RUN saved:{saved} missing:{missing} drift:{drift} "
        f"existing:{existing} unpairable:{unpairable}",
        flush=True,
    )
    print("BAO_EXSHADOW_POLICY=isolated_table_only_no_production_decision_change", flush=True)
    print("BAO_EXSHADOW_RESULT=PASS", flush=True)


if __name__ == "__main__":
    main()
