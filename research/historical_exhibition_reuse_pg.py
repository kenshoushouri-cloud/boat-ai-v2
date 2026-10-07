# -*- coding: utf-8 -*-
"""Reuse complete realtime exhibition snapshots as historical Exhibition Time.

Safety contract:
- candidate/research DB only (selected by workflow);
- no HTTP;
- no result/odds/payout reads;
- only snapshot_label='historical' in v2_realtime_exhibition_snapshots;
- fill missing Exhibition Time / rank / diff only;
- source must be one complete, internally valid realtime label;
- if learning_all and final_ab are both complete but disagree, skip the race.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, timedelta

import psycopg
from psycopg.rows import dict_row

WRITE_CONFIRM = "YES"
REUSE_SOURCE = "reused_realtime_exhibition_snapshot_v1"
SOURCE_LABELS = ("learning_all", "final_ab")


def _date_range(start_date: str, end_date: str) -> list[str]:
    a = date.fromisoformat(start_date)
    b = date.fromisoformat(end_date)
    if b < a:
        raise ValueError("end before start")
    out = []
    while a <= b:
        out.append(a.isoformat())
        a += timedelta(days=1)
    return out


def _stats_sql() -> str:
    return r"""
    with base as (
      select race_id, race_date
        from v2_races
       where race_date between %s and %s
    ),
    valid as (
      select e.race_id,
             e.snapshot_label,
             count(distinct e.lane) as lanes,
             count(*) filter (
               where e.exhibition_time >= 6.0 and e.exhibition_time < 8.0
             ) as valid_times,
             count(distinct e.exhibition_time_rank) filter (
               where e.exhibition_time_rank between 1 and 6
             ) as valid_ranks,
             count(*) filter (
               where e.exhibition_time_diff >= 0.0
                 and e.exhibition_time_diff < 2.0
             ) as valid_diffs
        from v2_realtime_exhibition_snapshots e
        join base b using(race_id)
       where e.snapshot_label in ('learning_all','final_ab')
         and e.lane between 1 and 6
       group by e.race_id,e.snapshot_label
    ),
    complete as (
      select race_id,snapshot_label
        from valid
       where lanes=6
         and valid_times=6
         and valid_ranks=6
         and valid_diffs=6
    ),
    conflicts as (
      select x.race_id, count(*)::int as conflict_lanes
        from (
          select e.race_id,e.lane,
                 max(e.exhibition_time) filter (
                   where e.snapshot_label='learning_all'
                 ) as learning_time,
                 max(e.exhibition_time) filter (
                   where e.snapshot_label='final_ab'
                 ) as final_time,
                 max(e.exhibition_time_rank) filter (
                   where e.snapshot_label='learning_all'
                 ) as learning_rank,
                 max(e.exhibition_time_rank) filter (
                   where e.snapshot_label='final_ab'
                 ) as final_rank,
                 max(e.exhibition_time_diff) filter (
                   where e.snapshot_label='learning_all'
                 ) as learning_diff,
                 max(e.exhibition_time_diff) filter (
                   where e.snapshot_label='final_ab'
                 ) as final_diff
            from v2_realtime_exhibition_snapshots e
            join base b using(race_id)
           where e.snapshot_label in ('learning_all','final_ab')
             and e.lane between 1 and 6
           group by e.race_id,e.lane
        ) x
        join complete l on l.race_id=x.race_id
                       and l.snapshot_label='learning_all'
        join complete f on f.race_id=x.race_id
                       and f.snapshot_label='final_ab'
       where abs(x.learning_time-x.final_time) > 0.000001
          or x.learning_rank <> x.final_rank
          or abs(x.learning_diff-x.final_diff) > 0.000001
       group by x.race_id
    ),
    chosen as (
      select b.race_id,b.race_date,
             case
               when l.race_id is not null
                and f.race_id is not null
                and coalesce(c.conflict_lanes,0) > 0 then null
               when l.race_id is not null then 'learning_all'
               when f.race_id is not null then 'final_ab'
               else null
             end as source_label,
             coalesce(c.conflict_lanes,0) as conflict_lanes
        from base b
        left join complete l on l.race_id=b.race_id
                            and l.snapshot_label='learning_all'
        left join complete f on f.race_id=b.race_id
                            and f.snapshot_label='final_ab'
        left join conflicts c on c.race_id=b.race_id
    ),
    hist as (
      select e.race_id,
             count(distinct e.lane) filter (
               where e.snapshot_label='historical'
                 and e.exhibition_time is not null
             ) as hist_times
        from v2_realtime_exhibition_snapshots e
        join base b using(race_id)
       group by e.race_id
    )
    select count(*)::int as races,
           count(*) filter(where chosen.source_label='learning_all')::int
             as reusable_learning,
           count(*) filter(where chosen.source_label='final_ab')::int
             as reusable_final,
           count(*) filter(where chosen.conflict_lanes>0)::int
             as conflicting_races,
           count(*) filter(where chosen.source_label is null
                            and chosen.conflict_lanes=0)::int
             as no_complete_source,
           count(*) filter(where coalesce(hist.hist_times,0)=6)::int
             as historical_complete_before,
           count(*) filter(where coalesce(hist.hist_times,0)<6
                            and chosen.source_label is not null)::int
             as reusable_missing_historical
      from chosen
      left join hist using(race_id)
    """


def _write_sql() -> str:
    return r"""
    with base as (
      select race_id,race_date,
             coalesce(venue_id,venue_code) as venue_id,
             race_no
        from v2_races
       where race_date between %s and %s
    ),
    valid as (
      select e.race_id,e.snapshot_label,
             count(distinct e.lane) as lanes,
             count(*) filter (
               where e.exhibition_time >= 6.0 and e.exhibition_time < 8.0
             ) as valid_times,
             count(distinct e.exhibition_time_rank) filter (
               where e.exhibition_time_rank between 1 and 6
             ) as valid_ranks,
             count(*) filter (
               where e.exhibition_time_diff >= 0.0
                 and e.exhibition_time_diff < 2.0
             ) as valid_diffs
        from v2_realtime_exhibition_snapshots e
        join base b using(race_id)
       where e.snapshot_label in ('learning_all','final_ab')
         and e.lane between 1 and 6
       group by e.race_id,e.snapshot_label
    ),
    complete as (
      select race_id,snapshot_label
        from valid
       where lanes=6 and valid_times=6 and valid_ranks=6 and valid_diffs=6
    ),
    conflicts as (
      select x.race_id
        from (
          select e.race_id,e.lane,
                 max(e.exhibition_time) filter (
                   where e.snapshot_label='learning_all'
                 ) as learning_time,
                 max(e.exhibition_time) filter (
                   where e.snapshot_label='final_ab'
                 ) as final_time,
                 max(e.exhibition_time_rank) filter (
                   where e.snapshot_label='learning_all'
                 ) as learning_rank,
                 max(e.exhibition_time_rank) filter (
                   where e.snapshot_label='final_ab'
                 ) as final_rank,
                 max(e.exhibition_time_diff) filter (
                   where e.snapshot_label='learning_all'
                 ) as learning_diff,
                 max(e.exhibition_time_diff) filter (
                   where e.snapshot_label='final_ab'
                 ) as final_diff
            from v2_realtime_exhibition_snapshots e
            join base b using(race_id)
           where e.snapshot_label in ('learning_all','final_ab')
             and e.lane between 1 and 6
           group by e.race_id,e.lane
        ) x
        join complete l on l.race_id=x.race_id
                       and l.snapshot_label='learning_all'
        join complete f on f.race_id=x.race_id
                       and f.snapshot_label='final_ab'
       where abs(x.learning_time-x.final_time) > 0.000001
          or x.learning_rank <> x.final_rank
          or abs(x.learning_diff-x.final_diff) > 0.000001
       group by x.race_id
    ),
    chosen as (
      select b.*,
             case
               when c.race_id is not null then null
               when l.race_id is not null then 'learning_all'
               when f.race_id is not null then 'final_ab'
               else null
             end as source_label
        from base b
        left join complete l on l.race_id=b.race_id
                            and l.snapshot_label='learning_all'
        left join complete f on f.race_id=b.race_id
                            and f.snapshot_label='final_ab'
        left join conflicts c on c.race_id=b.race_id
    ),
    source_rows as (
      select c.race_id,c.race_date,c.venue_id,c.race_no,c.source_label,
             e.snapshot_at,e.lane,
             e.exhibition_time,e.exhibition_time_rank,e.exhibition_time_diff
        from chosen c
        join v2_realtime_exhibition_snapshots e
          on e.race_id=c.race_id
         and e.snapshot_label=c.source_label
       where c.source_label is not null
         and e.lane between 1 and 6
    ),
    touched as (
      insert into v2_realtime_exhibition_snapshots(
        race_id,race_date,venue_id,venue_code,race_no,
        snapshot_label,snapshot_at,source,lane,
        exhibition_time,exhibition_time_rank,exhibition_time_diff,
        raw,updated_at
      )
      select s.race_id,s.race_date,
             lpad(s.venue_id::text,2,'0'),lpad(s.venue_id::text,2,'0'),
             s.race_no,
             'historical',s.snapshot_at,%s,s.lane,
             s.exhibition_time,s.exhibition_time_rank,s.exhibition_time_diff,
             jsonb_build_object(
               'reuse_contract','REALTIME_EXHIBITION_TO_HISTORICAL_V1',
               'source_snapshot_label',s.source_label,
               'source_snapshot_at',s.snapshot_at
             ),
             now()
        from source_rows s
      on conflict(race_id,snapshot_label,lane) do update set
        exhibition_time=coalesce(
          v2_realtime_exhibition_snapshots.exhibition_time,
          excluded.exhibition_time
        ),
        exhibition_time_rank=coalesce(
          v2_realtime_exhibition_snapshots.exhibition_time_rank,
          excluded.exhibition_time_rank
        ),
        exhibition_time_diff=coalesce(
          v2_realtime_exhibition_snapshots.exhibition_time_diff,
          excluded.exhibition_time_diff
        ),
        source=coalesce(v2_realtime_exhibition_snapshots.source,excluded.source),
        snapshot_at=coalesce(
          v2_realtime_exhibition_snapshots.snapshot_at,
          excluded.snapshot_at
        ),
        raw=coalesce(v2_realtime_exhibition_snapshots.raw,excluded.raw),
        updated_at=now()
      where
           (v2_realtime_exhibition_snapshots.exhibition_time is null
            and excluded.exhibition_time is not null)
        or (v2_realtime_exhibition_snapshots.exhibition_time_rank is null
            and excluded.exhibition_time_rank is not null)
        or (v2_realtime_exhibition_snapshots.exhibition_time_diff is null
            and excluded.exhibition_time_diff is not null)
      returning race_id,lane
    )
    select count(*)::int as rows_touched,
           count(distinct race_id)::int as races_touched
      from touched
    """


def _stats(conn, start_date: str, end_date: str) -> dict:
    return dict(conn.execute(_stats_sql(), (start_date, end_date)).fetchone())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", required=True)
    ap.add_argument("--end-date", required=True)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    dates = _date_range(args.start_date, args.end_date)
    if len(dates) > 32:
        raise SystemExit("maximum range is 32 days")

    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise SystemExit("DATABASE_URL required")

    write_enabled = (
        args.apply
        and os.getenv("CONFIRM_HISTORICAL_EXHIBITION_REUSE","").strip().upper()
        == WRITE_CONFIRM
    )
    if args.apply and not write_enabled:
        raise SystemExit("apply requires CONFIRM_HISTORICAL_EXHIBITION_REUSE=YES")

    with psycopg.connect(db,row_factory=dict_row,autocommit=False) as conn:
        if not write_enabled:
            conn.execute("SET TRANSACTION READ ONLY")
        before=_stats(conn,args.start_date,args.end_date)
        touched={"rows_touched":0,"races_touched":0}
        if write_enabled:
            touched=dict(conn.execute(
                _write_sql(),
                (args.start_date,args.end_date,REUSE_SOURCE),
            ).fetchone())
            conn.commit()
        else:
            conn.rollback()
        after=_stats(conn,args.start_date,args.end_date) if write_enabled else before
        if write_enabled:
            conn.rollback()

    print("HIST_REUSE_RANGE="+args.start_date+".."+args.end_date)
    print("HIST_REUSE_BEFORE="+json.dumps(before,sort_keys=True,separators=(",",":")))
    print("HIST_REUSE_TOUCHED="+json.dumps(touched,sort_keys=True,separators=(",",":")))
    print("HIST_REUSE_AFTER="+json.dumps(after,sort_keys=True,separators=(",",":")))
    print("HIST_REUSE_WRITE_ENABLED="+str(int(write_enabled)))
    print("HIST_REUSE_HTTP=0 RESULT_ODDS_PAYOUT_READ=0 PROD_MODEL_CHANGE=0 LINE=0 BUY=0")
    print("HIST_REUSE_RESULT=PASS")


if __name__ == "__main__":
    main()
