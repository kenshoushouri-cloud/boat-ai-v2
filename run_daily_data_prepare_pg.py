# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import runpy
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Any

JST = timezone(timedelta(hours=9))


def _connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL が未設定です")

    try:
        import psycopg  # type: ignore

        return psycopg.connect(url)
    except Exception:
        import psycopg2  # type: ignore

        return psycopg2.connect(url)


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }


def audit_target_date(target_date: str) -> None:
    """
    当日分の三連単オッズ品質を監査する。

    判定:
    - valid_tickets = 120:
        正常
    - valid_tickets = 1～119:
        取得不完全として問題
    - valid_tickets = 0 かつ締切済み:
        未取得として問題
    - valid_tickets = 0 かつ締切前:
        未発売・未取得待ちとして問題数から除外
    - invalid_rows > 0:
        ticket不正値として問題

    ODDS_IS_FINAL=True の場合は、締切前でも0件を問題として扱う。
    """
    odds_is_final = _env_bool("ODDS_IS_FINAL", False)
    now_jst = datetime.now(JST)

    sql = """
        WITH race_counts AS (
            SELECT
                r.race_id,
                r.venue_name,
                r.race_no,
                r.deadline_time,
                r.deadline_at,

                COUNT(DISTINCT o.ticket) FILTER (
                    WHERE o.ticket ~ '^[1-6]-[1-6]-[1-6]$'
                      AND split_part(o.ticket, '-', 1)
                          <> split_part(o.ticket, '-', 2)
                      AND split_part(o.ticket, '-', 1)
                          <> split_part(o.ticket, '-', 3)
                      AND split_part(o.ticket, '-', 2)
                          <> split_part(o.ticket, '-', 3)
                )::int AS valid_tickets,

                COUNT(*) FILTER (
                    WHERE o.ticket IS NOT NULL
                      AND (
                            o.ticket !~ '^[1-6]-[1-6]-[1-6]$'
                         OR split_part(o.ticket, '-', 1)
                            = split_part(o.ticket, '-', 2)
                         OR split_part(o.ticket, '-', 1)
                            = split_part(o.ticket, '-', 3)
                         OR split_part(o.ticket, '-', 2)
                            = split_part(o.ticket, '-', 3)
                      )
                )::int AS invalid_rows

            FROM v2_races r
            LEFT JOIN v2_odds_trifecta o
              ON o.race_id = r.race_id
            WHERE r.race_date = %s
            GROUP BY
                r.race_id,
                r.venue_name,
                r.race_no,
                r.deadline_time,
                r.deadline_at
        ),
        classified AS (
            SELECT
                race_id,
                venue_name,
                race_no,
                deadline_time,
                deadline_at,
                valid_tickets,
                invalid_rows,

                CASE
                    WHEN invalid_rows > 0
                        THEN 'invalid_ticket'

                    WHEN valid_tickets BETWEEN 1 AND 119
                        THEN 'partial_odds'

                    WHEN valid_tickets = 0
                         AND (
                                %s
                             OR (
                                    deadline_at IS NOT NULL
                                AND deadline_at <= %s
                             )
                         )
                        THEN 'missing_odds'

                    WHEN valid_tickets = 0
                        THEN 'pending'

                    WHEN valid_tickets = 120
                        THEN 'complete'

                    ELSE 'unexpected'
                END AS audit_status

            FROM race_counts
        )
        SELECT
            race_id,
            venue_name,
            race_no,
            deadline_time,
            deadline_at,
            valid_tickets,
            invalid_rows,
            audit_status
        FROM classified
        ORDER BY race_id
    """

    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    target_date,
                    odds_is_final,
                    now_jst,
                ),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    problem_rows: list[tuple[Any, ...]] = []
    pending_rows: list[tuple[Any, ...]] = []
    complete_count = 0

    for row in rows:
        status = row[7]

        if status == "complete":
            complete_count += 1
        elif status == "pending":
            pending_rows.append(row)
        else:
            problem_rows.append(row)

    partial_count = sum(
        1 for row in problem_rows if row[7] == "partial_odds"
    )
    missing_count = sum(
        1 for row in problem_rows if row[7] == "missing_odds"
    )
    invalid_count = sum(
        1 for row in problem_rows if row[7] == "invalid_ticket"
    )
    unexpected_count = sum(
        1 for row in problem_rows if row[7] == "unexpected"
    )

    print("=== daily odds quality audit ===", flush=True)
    print(f"target_date={target_date}", flush=True)
    print(
        f"audit_now_jst={now_jst.strftime('%Y-%m-%d %H:%M:%S%z')}",
        flush=True,
    )
    print(f"ODDS_IS_FINAL={odds_is_final}", flush=True)
    print(f"total_races={len(rows)}", flush=True)
    print(f"complete_races={complete_count}", flush=True)
    print(f"pending_races={len(pending_rows)}", flush=True)
    print(f"problem_races={len(problem_rows)}", flush=True)
    print(f"  partial_odds={partial_count}", flush=True)
    print(f"  missing_odds={missing_count}", flush=True)
    print(f"  invalid_ticket={invalid_count}", flush=True)
    print(f"  unexpected={unexpected_count}", flush=True)

    for (
        race_id,
        venue_name,
        race_no,
        deadline_time,
        deadline_at,
        valid_tickets,
        invalid_rows,
        audit_status,
    ) in problem_rows[:100]:
        print(
            "  "
            f"{race_id} "
            f"venue={venue_name} "
            f"race_no={race_no} "
            f"deadline_time={deadline_time} "
            f"deadline_at={deadline_at} "
            f"valid_tickets={valid_tickets} "
            f"invalid_rows={invalid_rows} "
            f"status={audit_status}",
            flush=True,
        )

    if len(problem_rows) > 100:
        print(
            f"  ... omitted={len(problem_rows) - 100}",
            flush=True,
        )


def main() -> None:
    print(
        "✅ run_daily_data_prepare_pg.py "
        "VERSION 2026-07-30-deadline-aware-odds-audit-v2",
        flush=True,
    )

    target_date = os.getenv("TARGET_DATE")
    if not target_date:
        target_date = datetime.now(JST).strftime("%Y-%m-%d")
        os.environ["TARGET_DATE"] = target_date

    os.environ["REPAIR_START_DATE"] = target_date
    os.environ["REPAIR_END_DATE"] = target_date
    os.environ["REPAIR_DO_RACES"] = "1"
    os.environ["REPAIR_DO_RESULTS"] = "0"
    os.environ["REPAIR_DO_ODDS"] = "1"

    os.environ.setdefault(
        "REPAIR_WORKERS",
        os.getenv("WORKERS", "4"),
    )
    os.environ.setdefault(
        "REPAIR_ODDS_WORKERS",
        os.getenv("ODDS_WORKERS", "2"),
    )
    os.environ.setdefault(
        "REPAIR_SLEEP_SEC",
        os.getenv("SLEEP_SEC", "0.1"),
    )

    print(f"TARGET_DATE={target_date}", flush=True)

    base_dir = Path(__file__).resolve().parent
    repair_path = base_dir / "repair_month_all_pg.py"

    if not repair_path.exists():
        raise FileNotFoundError(
            "repair_month_all_pg.py が見つかりません: "
            f"{repair_path}"
        )

    runpy.run_path(
        str(repair_path),
        run_name="__main__",
    )

    audit_target_date(target_date)


if __name__ == "__main__":
    main()