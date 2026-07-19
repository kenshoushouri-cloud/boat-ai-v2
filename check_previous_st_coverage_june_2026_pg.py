# -*- coding: utf-8 -*-
"""
check_previous_st_coverage_june_2026_pg.py

2026年6月分の前走ST保存状況を読み取り専用で確認します。
DB更新・LINE送信は行いません。

Railway Start Command:
    python -u check_previous_st_coverage_june_2026_pg.py

Variables:
    DATABASE_URL=${{postgres.DATABASE_URL}}
    CHECK_START_DATE=2026-06-01
    CHECK_END_DATE=2026-06-30
"""

from __future__ import annotations

import os
from typing import Any, Dict

from db_pg import fetch_all, fetch_one

START = os.getenv("CHECK_START_DATE", "2026-06-01")
END = os.getenv("CHECK_END_DATE", "2026-06-30")


def d(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return {"value": row}


def print_row(prefix: str, row: Any) -> None:
    x = d(row)
    body = " ".join(f"{k}={v}" for k, v in x.items())
    print(f"{prefix}{body}", flush=True)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ check_previous_st_coverage_june_2026_pg.py VERSION 2026-07-20 june-audit-v1", flush=True)
    print(f"PERIOD={START}..{END}", flush=True)
    print("読み取り専用です。DB更新・LINE送信は行いません。", flush=True)

    print("\n=== OVERALL ===", flush=True)
    overall = fetch_one(
        """
        with race_base as (
          select
            r.race_id,
            count(distinct e.lane) entries_count,
            max(case when rs.first_lane is not null
                       and rs.second_lane is not null
                       and rs.third_lane is not null
                     then 1 else 0 end) result_ok
          from v2_races r
          left join v2_race_entries e on e.race_id=r.race_id
          left join v2_results rs on rs.race_id=r.race_id
          where r.race_date between %s and %s
          group by r.race_id
        ),
        latest_st as (
          select *
          from (
            select
              s.race_id,
              s.lane,
              s.previous_st,
              s.snapshot_label,
              row_number() over (
                partition by s.race_id, s.lane, s.snapshot_label
                order by s.snapshot_at desc nulls last, s.id desc
              ) rn
            from v2_realtime_racer_condition_snapshots s
            join v2_races r on r.race_id=s.race_id
            where r.race_date between %s and %s
          ) z
          where rn=1
        ),
        st_race as (
          select
            race_id,
            count(*) rows_latest,
            count(previous_st) previous_st_nonnull,
            count(distinct lane) lanes,
            count(distinct lane) filter (where previous_st is not null) st_lanes,
            count(distinct snapshot_label) labels
          from latest_st
          group by race_id
        )
        select
          count(*) total_races,
          count(*) filter (where rb.entries_count=6) entries_full_races,
          count(*) filter (where rb.result_ok=1) result_ok_races,
          count(sr.race_id) snapshot_races,
          count(*) filter (where sr.lanes=6) snapshot_6lane_races,
          count(*) filter (where sr.st_lanes=6) previous_st_6lane_races,
          count(*) filter (where sr.st_lanes between 1 and 5) previous_st_partial_races,
          count(*) filter (where coalesce(sr.st_lanes,0)=0) previous_st_zero_races
        from race_base rb
        left join st_race sr on sr.race_id=rb.race_id;
        """,
        (START, END, START, END),
    )
    print_row("", overall)

    print("\n=== BY SNAPSHOT LABEL ===", flush=True)
    rows = fetch_all(
        """
        select
          coalesce(s.snapshot_label, '(null)') snapshot_label,
          count(*) rows,
          count(s.previous_st) previous_st_nonnull,
          count(distinct s.race_id) races,
          count(distinct s.race_id) filter (where s.previous_st is not null) previous_st_races,
          min(s.previous_st) min_st,
          max(s.previous_st) max_st,
          avg(s.previous_st) avg_st
        from v2_realtime_racer_condition_snapshots s
        join v2_races r on r.race_id=s.race_id
        where r.race_date between %s and %s
        group by coalesce(s.snapshot_label, '(null)')
        order by snapshot_label;
        """,
        (START, END),
    )
    if not rows:
        print("snapshot rows=0", flush=True)
    for row in rows:
        print_row("", row)

    print("\n=== BY DAY ===", flush=True)
    rows = fetch_all(
        """
        with latest_st as (
          select *
          from (
            select
              r.race_date,
              s.race_id,
              s.lane,
              s.previous_st,
              row_number() over (
                partition by s.race_id, s.lane
                order by s.snapshot_at desc nulls last, s.id desc
              ) rn
            from v2_realtime_racer_condition_snapshots s
            join v2_races r on r.race_id=s.race_id
            where r.race_date between %s and %s
          ) z
          where rn=1
        ),
        races as (
          select race_date, count(*) races
          from v2_races
          where race_date between %s and %s
          group by race_date
        ),
        st as (
          select
            race_date,
            count(*) snapshot_rows,
            count(previous_st) previous_st_nonnull,
            count(distinct race_id) snapshot_races,
            count(distinct race_id) filter (where previous_st is not null) previous_st_races
          from latest_st
          group by race_date
        )
        select
          r.race_date,
          r.races,
          coalesce(st.snapshot_races,0) snapshot_races,
          coalesce(st.previous_st_races,0) previous_st_races,
          coalesce(st.snapshot_rows,0) snapshot_rows,
          coalesce(st.previous_st_nonnull,0) previous_st_nonnull
        from races r
        left join st on st.race_date=r.race_date
        order by r.race_date;
        """,
        (START, END, START, END),
    )
    for row in rows:
        print_row("", row)

    print("\n=== BY VENUE ===", flush=True)
    rows = fetch_all(
        """
        with latest_st as (
          select *
          from (
            select
              r.venue_id,
              s.race_id,
              s.lane,
              s.previous_st,
              row_number() over (
                partition by s.race_id, s.lane
                order by s.snapshot_at desc nulls last, s.id desc
              ) rn
            from v2_realtime_racer_condition_snapshots s
            join v2_races r on r.race_id=s.race_id
            where r.race_date between %s and %s
          ) z
          where rn=1
        ),
        races as (
          select venue_id, count(*) races
          from v2_races
          where race_date between %s and %s
          group by venue_id
        ),
        st as (
          select
            venue_id,
            count(distinct race_id) snapshot_races,
            count(distinct race_id) filter (where previous_st is not null) previous_st_races,
            count(*) snapshot_rows,
            count(previous_st) previous_st_nonnull
          from latest_st
          group by venue_id
        )
        select
          lpad(r.venue_id::text,2,'0') venue_id,
          r.races,
          coalesce(st.snapshot_races,0) snapshot_races,
          coalesce(st.previous_st_races,0) previous_st_races,
          coalesce(st.snapshot_rows,0) snapshot_rows,
          coalesce(st.previous_st_nonnull,0) previous_st_nonnull
        from races r
        left join st on st.venue_id=r.venue_id
        order by r.venue_id;
        """,
        (START, END, START, END),
    )
    for row in rows:
        print_row("", row)

    print("\n=== DUPLICATES ===", flush=True)
    row = fetch_one(
        """
        select
          count(*) duplicate_groups,
          coalesce(sum(n-1),0) extra_rows,
          max(n) max_rows_per_race_lane_label
        from (
          select s.race_id, s.lane, s.snapshot_label, count(*) n
          from v2_realtime_racer_condition_snapshots s
          join v2_races r on r.race_id=s.race_id
          where r.race_date between %s and %s
          group by s.race_id, s.lane, s.snapshot_label
          having count(*) > 1
        ) q;
        """,
        (START, END),
    )
    print_row("", row)

    print("\n=== MISSING / PARTIAL SAMPLE ===", flush=True)
    rows = fetch_all(
        """
        with latest_st as (
          select *
          from (
            select
              s.race_id,
              s.lane,
              s.previous_st,
              row_number() over (
                partition by s.race_id, s.lane
                order by s.snapshot_at desc nulls last, s.id desc
              ) rn
            from v2_realtime_racer_condition_snapshots s
            join v2_races r0 on r0.race_id=s.race_id
            where r0.race_date between %s and %s
          ) z
          where rn=1
        ),
        st_race as (
          select
            race_id,
            count(distinct lane) lanes,
            count(distinct lane) filter (where previous_st is not null) st_lanes
          from latest_st
          group by race_id
        )
        select
          r.race_date,
          r.race_id,
          lpad(r.venue_id::text,2,'0') venue_id,
          r.race_no,
          coalesce(sr.lanes,0) snapshot_lanes,
          coalesce(sr.st_lanes,0) previous_st_lanes
        from v2_races r
        left join st_race sr on sr.race_id=r.race_id
        where r.race_date between %s and %s
          and coalesce(sr.st_lanes,0) < 6
        order by r.race_date, r.venue_id, r.race_no
        limit 100;
        """,
        (START, END, START, END),
    )
    if not rows:
        print("6艇分のprevious_stが全レースで揃っています。", flush=True)
    for row in rows:
        print_row("", row)

    print("\n=== JUNE AUDIT FINISHED ===", flush=True)


if __name__ == "__main__":
    main()