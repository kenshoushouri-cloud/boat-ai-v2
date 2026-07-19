# -*- coding: utf-8 -*-
"""
diagnose_previous_st_sources_pg.py

前走ST・展示ST・結果着順の実保存元を特定する読み取り専用診断。
DB更新・LINE送信なし。

Railway Start Command:
    python -u diagnose_previous_st_sources_pg.py

Variables:
    DATABASE_URL
    DIAG_START_DATE=2026-01-01
    DIAG_END_DATE=2026-03-31
    DIAG_SAMPLE_LIMIT=8
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Sequence

from db_pg import fetch_all, fetch_one

JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime("%Y-%m-%d")
START_DATE = os.getenv("DIAG_START_DATE") or os.getenv("FEATURE_LAB_START_DATE") or TODAY
END_DATE = os.getenv("DIAG_END_DATE") or os.getenv("FEATURE_LAB_END_DATE") or TODAY
LIMIT = max(3, int(os.getenv("DIAG_SAMPLE_LIMIT", "8")))

CORE_TABLES = [
    "v2_races",
    "v2_race_entries",
    "v2_results",
    "v2_exhibition",
    "v2_feature_snapshots",
    "v2_realtime_decisions",
    "v2_realtime_racer_condition_snapshots",
    "v2_realtime_exhibition_snapshots",
    "v2_previous_st_shadow_rankings",
    "v2_feature_lab_results",
]


def exists(table: str) -> bool:
    row = fetch_one(
        """select exists(
             select 1 from information_schema.tables
             where table_schema='public' and table_name=%s
           ) ok;""",
        (table,),
    )
    return bool(row and row.get("ok"))


def cols(table: str) -> List[str]:
    rows = fetch_all(
        """select column_name from information_schema.columns
           where table_schema='public' and table_name=%s
           order by ordinal_position;""",
        (table,),
    )
    return [str(r["column_name"]) for r in rows]


def pick(columns: Sequence[str], names: Sequence[str]) -> str | None:
    s = set(columns)
    return next((x for x in names if x in s), None)


def pretty(v: Any, max_len: int = 1000) -> str:
    try:
        if isinstance(v, (dict, list)):
            text = json.dumps(v, ensure_ascii=False, default=str)
        else:
            text = str(v)
    except Exception:
        text = repr(v)
    return text[:max_len]


def date_column(columns: Sequence[str]) -> str | None:
    return pick(columns, ["race_date", "target_date", "date"])


def print_table_inventory(table: str) -> None:
    print("\n" + "=" * 88, flush=True)
    print(f"TABLE={table}", flush=True)
    if not exists(table):
        print("exists=NO", flush=True)
        return

    c = cols(table)
    print(f"exists=YES columns({len(c)})={', '.join(c)}", flush=True)

    dcol = date_column(c)
    if dcol:
        row = fetch_one(
            f"""select count(*) n, min({dcol}) min_date, max({dcol}) max_date
                from {table}
                where {dcol} >= %s and {dcol} <= %s;""",
            (START_DATE, END_DATE),
        ) or {}
    elif "race_id" in c:
        row = fetch_one(
            f"""select count(*) n
                from {table} t
                join v2_races r on r.race_id=t.race_id
                where r.race_date >= %s and r.race_date <= %s;""",
            (START_DATE, END_DATE),
        ) or {}
    else:
        row = fetch_one(f"select count(*) n from {table};") or {}

    print(f"period_rows={row.get('n')} min_date={row.get('min_date')} max_date={row.get('max_date')}", flush=True)

    interesting = [
        x for x in c
        if any(k in x.lower() for k in (
            "st", "start", "timing", "result", "finish", "rank", "arrival",
            "first", "second", "third", "raw", "recent", "snapshot",
            "racer", "lane", "course", "class"
        ))
    ]
    print(f"interesting_columns={', '.join(interesting) if interesting else 'NONE'}", flush=True)


def sample_recent_form() -> None:
    if not exists("v2_race_entries"):
        return
    c = cols("v2_race_entries")
    if "recent_form" not in c:
        return

    rows = fetch_all(
        """select e.race_id, r.race_date, e.lane,
                  coalesce(e.racer_number::text, e.racer_no::text) as racer_number,
                  e.avg_st, e.racer_class, e.racer_class_text, e.recent_form, e.raw
           from v2_race_entries e
           join v2_races r on r.race_id=e.race_id
           where r.race_date >= %s and r.race_date <= %s
           order by r.race_date, e.race_id, e.lane
           limit %s;""",
        (START_DATE, END_DATE, LIMIT),
    )
    print("\n=== v2_race_entries SAMPLE ===", flush=True)
    for r in rows:
        print(
            f"race_id={r.get('race_id')} date={r.get('race_date')} lane={r.get('lane')} "
            f"racer={r.get('racer_number')} class={r.get('racer_class')}/"
            f"{r.get('racer_class_text')} avg_st={r.get('avg_st')}",
            flush=True,
        )
        print(f"  recent_form={pretty(r.get('recent_form'))}", flush=True)
        print(f"  raw={pretty(r.get('raw'))}", flush=True)


def sample_results() -> None:
    if not exists("v2_results"):
        return
    c = cols("v2_results")
    select_cols = [x for x in (
        "race_id", "race_date", "first_lane", "second_lane", "third_lane",
        "trifecta_ticket", "result_status", "race_status", "raw"
    ) if x in c]
    if not select_cols:
        select_cols = c[:12]

    dcol = date_column(c)
    if dcol:
        rows = fetch_all(
            f"""select {', '.join(select_cols)}
                from v2_results
                where {dcol} >= %s and {dcol} <= %s
                order by {dcol}, race_id
                limit %s;""",
            (START_DATE, END_DATE, LIMIT),
        )
    else:
        rows = fetch_all(
            f"""select {', '.join('rs.' + x for x in select_cols)}
                from v2_results rs
                join v2_races r on r.race_id=rs.race_id
                where r.race_date >= %s and r.race_date <= %s
                order by r.race_date, rs.race_id
                limit %s;""",
            (START_DATE, END_DATE, LIMIT),
        )

    print("\n=== v2_results SAMPLE ===", flush=True)
    for r in rows:
        print(pretty(r, 1600), flush=True)


def sample_exhibition() -> None:
    if not exists("v2_exhibition"):
        return
    c = cols("v2_exhibition")
    stcol = pick(c, ["start_timing", "exhibition_st", "tenji_st"])
    lanecol = pick(c, ["lane", "course", "boat_no"])

    total = fetch_one(
        """select count(*) n, count(distinct e.race_id) races
           from v2_exhibition e
           join v2_races r on r.race_id=e.race_id
           where r.race_date >= %s and r.race_date <= %s;""",
        (START_DATE, END_DATE),
    ) or {}
    print("\n=== v2_exhibition COVERAGE ===", flush=True)
    print(f"rows={total.get('n')} distinct_races={total.get('races')} stcol={stcol} lanecol={lanecol}", flush=True)

    if stcol:
        nonnull = fetch_one(
            f"""select count(*) n
                from v2_exhibition e
                join v2_races r on r.race_id=e.race_id
                where r.race_date >= %s and r.race_date <= %s
                  and e.{stcol} is not null;""",
            (START_DATE, END_DATE),
        ) or {}
        print(f"{stcol}_nonnull={nonnull.get('n')}", flush=True)

    rows = fetch_all(
        """select e.*
           from v2_exhibition e
           join v2_races r on r.race_id=e.race_id
           where r.race_date >= %s and r.race_date <= %s
           order by r.race_date, e.race_id
           limit %s;""",
        (START_DATE, END_DATE, LIMIT),
    )
    for r in rows:
        print(pretty(r, 1600), flush=True)


def discover_st_like_columns() -> None:
    rows = fetch_all(
        """select table_name, column_name, data_type
           from information_schema.columns
           where table_schema='public'
             and (
               lower(column_name) like '%%st%%'
               or lower(column_name) like '%%start%%'
               or lower(column_name) like '%%timing%%'
               or lower(column_name) like '%%finish%%'
               or lower(column_name) like '%%arrival%%'
             )
           order by table_name, ordinal_position;"""
    )
    print("\n=== ALL ST/RESULT-LIKE COLUMNS ===", flush=True)
    for r in rows:
        print(f"{r.get('table_name')}.{r.get('column_name')} ({r.get('data_type')})", flush=True)


def discover_json_keys() -> None:
    print("\n=== JSON KEY DISCOVERY ===", flush=True)
    targets = []
    for table in CORE_TABLES:
        if not exists(table):
            continue
        for c in cols(table):
            dt = fetch_one(
                """select data_type
                   from information_schema.columns
                   where table_schema='public' and table_name=%s and column_name=%s;""",
                (table, c),
            )
            if dt and str(dt.get("data_type")) in ("json", "jsonb"):
                targets.append((table, c))

    for table, col in targets:
        if "race_id" in cols(table):
            rows = fetch_all(
                f"""select distinct jsonb_object_keys(
                       case when jsonb_typeof({col}::jsonb)='object'
                            then {col}::jsonb else '{{}}'::jsonb end
                     ) as key
                    from {table} t
                    join v2_races r on r.race_id=t.race_id
                    where r.race_date >= %s and r.race_date <= %s
                    order by key
                    limit 100;""",
                (START_DATE, END_DATE),
            )
        else:
            rows = fetch_all(
                f"""select distinct jsonb_object_keys(
                       case when jsonb_typeof({col}::jsonb)='object'
                            then {col}::jsonb else '{{}}'::jsonb end
                     ) as key
                    from {table}
                    order by key
                    limit 100;"""
            )
        keys = [str(r.get("key")) for r in rows if r.get("key") is not None]
        print(f"{table}.{col}: {', '.join(keys) if keys else 'NO_OBJECT_KEYS'}", flush=True)


def same_racer_history_sample() -> None:
    if not exists("v2_race_entries"):
        return
    c = cols("v2_race_entries")
    racer_col = pick(c, ["racer_number", "racer_no", "registration_no", "racer_id"])
    if not racer_col:
        return

    row = fetch_one(
        f"""select e.{racer_col} racer
            from v2_race_entries e
            join v2_races r on r.race_id=e.race_id
            where r.race_date >= %s and r.race_date <= %s
              and e.{racer_col} is not null
            group by e.{racer_col}
            having count(*) >= 3
            order by count(*) desc
            limit 1;""",
        (START_DATE, END_DATE),
    )
    if not row:
        return

    racer = row.get("racer")
    rows = fetch_all(
        f"""select r.race_date, r.venue_id, r.race_no,
                   e.race_id, e.lane, e.{racer_col} racer,
                   e.avg_st, e.racer_class, e.racer_class_text,
                   e.recent_form, e.raw,
                   rs.first_lane, rs.second_lane, rs.third_lane,
                   rs.raw result_raw
            from v2_race_entries e
            join v2_races r on r.race_id=e.race_id
            left join v2_results rs on rs.race_id=e.race_id
            where e.{racer_col}=%s
              and r.race_date >= %s and r.race_date <= %s
            order by r.race_date, r.race_id
            limit 20;""",
        (racer, START_DATE, END_DATE),
    )
    print("\n=== SAME RACER CHRONOLOGY SAMPLE ===", flush=True)
    print(f"racer={racer}", flush=True)
    for r in rows:
        print(pretty(r, 1800), flush=True)


def focused_previous_st_sources() -> None:
    print("\n=== FOCUSED PREVIOUS ST SOURCES ===", flush=True)

    if exists("v2_realtime_racer_condition_snapshots"):
        c = cols("v2_realtime_racer_condition_snapshots")
        print(
            "v2_realtime_racer_condition_snapshots columns="
            + ", ".join(c),
            flush=True,
        )
        rows = fetch_all(
            """select s.*
               from v2_realtime_racer_condition_snapshots s
               join v2_races r on r.race_id=s.race_id
               where r.race_date >= %s and r.race_date <= %s
               order by r.race_date, s.race_id
               limit %s;""",
            (START_DATE, END_DATE, LIMIT),
        )
        print(f"period_sample_rows={len(rows)}", flush=True)
        for row in rows:
            print(pretty(row, 1800), flush=True)

        if "previous_st" in c:
            stat = fetch_one(
                """select count(*) rows,
                          count(*) filter (where s.previous_st is not null) previous_st_nonnull,
                          count(distinct s.race_id) filter (where s.previous_st is not null) previous_st_races,
                          min(s.previous_st) min_st,
                          max(s.previous_st) max_st,
                          avg(s.previous_st) avg_st
                   from v2_realtime_racer_condition_snapshots s
                   join v2_races r on r.race_id=s.race_id
                   where r.race_date >= %s and r.race_date <= %s;""",
                (START_DATE, END_DATE),
            ) or {}
            print("previous_st_stats=" + pretty(stat, 1200), flush=True)

    if exists("v2_previous_st_shadow_rankings"):
        c = cols("v2_previous_st_shadow_rankings")
        print(
            "v2_previous_st_shadow_rankings columns="
            + ", ".join(c),
            flush=True,
        )
        dcol = date_column(c)
        if dcol:
            rows = fetch_all(
                f"""select *
                    from v2_previous_st_shadow_rankings
                    where {dcol} >= %s and {dcol} <= %s
                    order by {dcol}
                    limit %s;""",
                (START_DATE, END_DATE, LIMIT),
            )
        elif "race_id" in c:
            rows = fetch_all(
                """select s.*
                   from v2_previous_st_shadow_rankings s
                   join v2_races r on r.race_id=s.race_id
                   where r.race_date >= %s and r.race_date <= %s
                   order by r.race_date, s.race_id
                   limit %s;""",
                (START_DATE, END_DATE, LIMIT),
            )
        else:
            rows = fetch_all(
                "select * from v2_previous_st_shadow_rankings limit %s;",
                (LIMIT,),
            )
        for row in rows:
            print(pretty(row, 1800), flush=True)

    if exists("v2_feature_lab_results"):
        c = cols("v2_feature_lab_results")
        print("v2_feature_lab_results columns=" + ", ".join(c), flush=True)
        rows = fetch_all(
            """select *
               from v2_feature_lab_results
               order by created_at desc nulls last
               limit %s;""",
            (LIMIT,),
        )
        for row in rows:
            print(pretty(row, 2200), flush=True)

    if exists("v2_realtime_exhibition_snapshots"):
        c = cols("v2_realtime_exhibition_snapshots")
        print(
            "v2_realtime_exhibition_snapshots columns="
            + ", ".join(c),
            flush=True,
        )
        rows = fetch_all(
            """select s.*
               from v2_realtime_exhibition_snapshots s
               join v2_races r on r.race_id=s.race_id
               where r.race_date >= %s and r.race_date <= %s
               order by r.race_date, s.race_id
               limit %s;""",
            (START_DATE, END_DATE, LIMIT),
        )
        print(f"period_sample_rows={len(rows)}", flush=True)
        for row in rows:
            print(pretty(row, 1800), flush=True)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ diagnose_previous_st_sources_pg.py VERSION 2026-07-20 source-audit-v2", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} SAMPLE_LIMIT={LIMIT}", flush=True)
    print("読み取り専用です。DB更新・LINE送信は行いません。", flush=True)

    for table in CORE_TABLES:
        print_table_inventory(table)

    discover_st_like_columns()
    sample_recent_form()
    sample_results()
    sample_exhibition()
    discover_json_keys()
    same_racer_history_sample()
    focused_previous_st_sources()

    print("\n=== source audit finished ===", flush=True)


if __name__ == "__main__":
    main()