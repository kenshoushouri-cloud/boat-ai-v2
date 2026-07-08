# -*- coding: utf-8 -*-
"""
pg_backtest_ready_check.py

Railway Postgres用 readiness確認 fix1。

fix1:
- v2_results.result_status が未設定でも、3連単結果と払戻が入っていれば result_ok と判定。
- result_status の分布も表示。
- odds 120通り未満のレースも確認。

Railway Start Command:
    python -u pg_backtest_ready_check.py

Variables:
    DATABASE_URL=${{postgres.DATABASE_URL}}
    CHECK_START_DATE=2026-06-01
    CHECK_END_DATE=2026-07-07
"""

from __future__ import annotations

import os
from typing import Any

from db_pg import fetch_all, fetch_one

START_DATE = os.getenv("CHECK_START_DATE", "2026-06-01")
END_DATE = os.getenv("CHECK_END_DATE", "2026-07-07")


def _safe_int(v: Any) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("=== PG backtest readiness check fix1 ===", flush=True)
    print(f"CHECK_START_DATE={START_DATE} CHECK_END_DATE={END_DATE}", flush=True)

    status_rows = fetch_all(
        """
        select
            coalesce(result_status, '(null)') as result_status,
            count(*) as rows
        from v2_results
        where race_id >= replace(%s, '-', '')
          and race_id < replace((%s::date + interval '1 day')::date::text, '-', '')
        group by coalesce(result_status, '(null)')
        order by rows desc;
        """,
        (START_DATE, END_DATE),
    )
    print("\n--- result_status distribution ---", flush=True)
    if not status_rows:
        print("v2_resultsなし", flush=True)
    else:
        for r in status_rows:
            print(f"{r['result_status']}: {_safe_int(r.get('rows'))}", flush=True)

    total = fetch_one(
        """
        with race_base as (
            select
                r.race_id,
                r.race_date,
                r.venue_id,
                r.race_no,
                count(distinct e.lane) as entries_count,
                count(distinct o.ticket) as odds_count,
                max(case
                    when coalesce(res.trifecta_payout_yen, 0) > 0
                     and (
                        coalesce(nullif(res.trifecta_ticket, ''), '') <> ''
                        or (
                            res.first_lane is not null
                            and res.second_lane is not null
                            and res.third_lane is not null
                        )
                     )
                    then 1 else 0 end) as result_ok
            from v2_races r
            left join v2_race_entries e on e.race_id = r.race_id
            left join v2_odds_trifecta o on o.race_id = r.race_id
            left join v2_results res on res.race_id = r.race_id
            where r.race_date between %s and %s
            group by r.race_id, r.race_date, r.venue_id, r.race_no
        )
        select
            count(*) as total_races,
            sum(case when entries_count = 6 then 1 else 0 end) as entries_full,
            sum(case when result_ok = 1 then 1 else 0 end) as result_ok,
            sum(case when odds_count = 120 then 1 else 0 end) as odds_full_120,
            sum(case when entries_count = 6 and result_ok = 1 and odds_count = 120 then 1 else 0 end) as backtest_ready,
            sum(greatest(0, 120 - odds_count)) as missing_odds_rows
        from race_base;
        """,
        (START_DATE, END_DATE),
    )

    print("\n--- total ---", flush=True)
    for k in ["total_races", "entries_full", "result_ok", "odds_full_120", "backtest_ready", "missing_odds_rows"]:
        print(f"{k}: {_safe_int(total.get(k))}", flush=True)

    monthly = fetch_all(
        """
        with race_base as (
            select
                to_char(r.race_date, 'YYYY-MM') as month,
                r.race_id,
                count(distinct e.lane) as entries_count,
                count(distinct o.ticket) as odds_count,
                max(case
                    when coalesce(res.trifecta_payout_yen, 0) > 0
                     and (
                        coalesce(nullif(res.trifecta_ticket, ''), '') <> ''
                        or (
                            res.first_lane is not null
                            and res.second_lane is not null
                            and res.third_lane is not null
                        )
                     )
                    then 1 else 0 end) as result_ok
            from v2_races r
            left join v2_race_entries e on e.race_id = r.race_id
            left join v2_odds_trifecta o on o.race_id = r.race_id
            left join v2_results res on res.race_id = r.race_id
            where r.race_date between %s and %s
            group by to_char(r.race_date, 'YYYY-MM'), r.race_id
        )
        select
            month,
            count(*) as total_races,
            sum(case when entries_count = 6 then 1 else 0 end) as entries_full,
            sum(case when result_ok = 1 then 1 else 0 end) as result_ok,
            sum(case when odds_count = 120 then 1 else 0 end) as odds_full_120,
            sum(case when entries_count = 6 and result_ok = 1 and odds_count = 120 then 1 else 0 end) as backtest_ready,
            sum(greatest(0, 120 - odds_count)) as missing_odds_rows
        from race_base
        group by month
        order by month;
        """,
        (START_DATE, END_DATE),
    )

    print("\n--- monthly ---", flush=True)
    for r in monthly:
        print(
            f"{r['month']}: total={_safe_int(r.get('total_races'))} "
            f"entries_full={_safe_int(r.get('entries_full'))} "
            f"result_ok={_safe_int(r.get('result_ok'))} "
            f"odds_full_120={_safe_int(r.get('odds_full_120'))} "
            f"backtest_ready={_safe_int(r.get('backtest_ready'))} "
            f"missing_odds_rows={_safe_int(r.get('missing_odds_rows'))}",
            flush=True,
        )

    worst = fetch_all(
        """
        select
            r.race_id,
            r.race_date,
            r.venue_id,
            r.race_no,
            count(distinct o.ticket) as odds_count,
            greatest(0, 120 - count(distinct o.ticket)) as missing_odds
        from v2_races r
        left join v2_odds_trifecta o on o.race_id = r.race_id
        where r.race_date between %s and %s
        group by r.race_id, r.race_date, r.venue_id, r.race_no
        having count(distinct o.ticket) < 120
        order by missing_odds desc, r.race_date asc, r.venue_id asc, r.race_no asc
        limit 40;
        """,
        (START_DATE, END_DATE),
    )

    print("\n--- odds missing worst 40 ---", flush=True)
    if not worst:
        print("odds欠けなし", flush=True)
    else:
        for r in worst:
            print(
                f"{r['race_id']} date={r['race_date']} venue={str(r['venue_id']).zfill(2)} "
                f"R{r['race_no']} odds={_safe_int(r.get('odds_count'))}/120 "
                f"missing={_safe_int(r.get('missing_odds'))}",
                flush=True,
            )

    print("=== readiness check finished ===", flush=True)


if __name__ == "__main__":
    main()