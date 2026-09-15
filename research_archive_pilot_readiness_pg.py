# -*- coding: utf-8 -*-
"""Read-only archive-pilot readiness audit.

This helper ranks completed calendar months for a future export/readback-only
pilot. It never exports, deletes, updates, creates, or uploads data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import calendar
import os
from typing import Any, Iterable

JST = timezone(timedelta(hours=9))
DEFAULT_LOOKBACK_MONTHS = 12
DEFAULT_MIN_AGE_DAYS = 30


@dataclass(frozen=True)
class MonthReadiness:
    month: str
    start_date: date
    end_date: date
    race_count: int
    result_races: int
    full_result_entry_races: int
    base_odds_races: int
    full_120_base_odds_races: int
    historical_weather_races: int
    historical_exhibition_races: int
    historical_exhibition_full6_races: int

    @property
    def results_complete(self) -> bool:
        return self.race_count > 0 and self.result_races == self.race_count

    @property
    def result_entries_complete(self) -> bool:
        return self.race_count > 0 and self.full_result_entry_races == self.race_count

    @property
    def settled(self) -> bool:
        return self.results_complete and self.result_entries_complete

    @property
    def pilot_score(self) -> tuple[int, int, int, int]:
        """Deterministic preference: settled, then evidence richness, then size."""
        historical_richness = self.historical_weather_races + self.historical_exhibition_full6_races
        odds_richness = self.full_120_base_odds_races
        return (int(self.settled), historical_richness, odds_richness, self.race_count)


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def shift_month(first: date, delta: int) -> date:
    absolute = first.year * 12 + (first.month - 1) + delta
    year, month0 = divmod(absolute, 12)
    return date(year, month0 + 1, 1)


def candidate_months(
    *,
    today: date,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    min_age_days: int = DEFAULT_MIN_AGE_DAYS,
) -> list[tuple[date, date]]:
    if lookback_months <= 0:
        raise ValueError("lookback_months must be positive")
    if min_age_days < 0:
        raise ValueError("min_age_days must be >= 0")
    current = date(today.year, today.month, 1)
    latest_allowed = today - timedelta(days=min_age_days)
    out: list[tuple[date, date]] = []
    for back in range(1, lookback_months + 1):
        first = shift_month(current, -back)
        start, end = month_bounds(first.year, first.month)
        if end <= latest_allowed:
            out.append((start, end))
    return out


def _scalar(cur: Any, sql: str, params: Iterable[Any]) -> int:
    cur.execute(sql, tuple(params))
    row = cur.fetchone()
    return int((row[0] if row else 0) or 0)


def _table_exists(cur: Any, table: str) -> bool:
    cur.execute(
        "select exists(select 1 from information_schema.tables where table_schema='public' and table_name=%s)",
        (table,),
    )
    row = cur.fetchone()
    return bool(row and row[0])


def _column_exists(cur: Any, table: str, column: str) -> bool:
    cur.execute(
        "select exists(select 1 from information_schema.columns where table_schema='public' and table_name=%s and column_name=%s)",
        (table, column),
    )
    row = cur.fetchone()
    return bool(row and row[0])


def _race_bounds(start: date, end: date) -> tuple[str, str]:
    return start.strftime("%Y%m%d"), (end + timedelta(days=1)).strftime("%Y%m%d")


def audit_month(conn: Any, start: date, end: date) -> MonthReadiness:
    with conn.cursor() as cur:
        for required in ("v2_races", "v2_results", "v2_result_entries", "v2_odds_trifecta"):
            if not _table_exists(cur, required):
                raise RuntimeError(f"required table is missing: {required}")

        races = _scalar(
            cur,
            "select count(distinct race_id) from v2_races where race_date >= %s and race_date <= %s",
            (start, end),
        )
        results = _scalar(
            cur,
            """select count(distinct x.race_id)
               from v2_results x join v2_races r on r.race_id=x.race_id
               where r.race_date >= %s and r.race_date <= %s""",
            (start, end),
        )

        result_lane_col = next(
            (
                c
                for c in ("lane", "course", "boat_no")
                if _column_exists(cur, "v2_result_entries", c)
            ),
            None,
        )
        if not result_lane_col:
            raise RuntimeError("v2_result_entries has no supported lane column")
        full_results = _scalar(
            cur,
            f"""select count(*) from (
                    select x.race_id
                    from v2_result_entries x join v2_races r on r.race_id=x.race_id
                    where r.race_date >= %s and r.race_date <= %s
                    group by x.race_id
                    having count(distinct x.{result_lane_col}) = 6
                ) q""",
            (start, end),
        )

        rid_start, rid_end = _race_bounds(start, end)
        base_odds = _scalar(
            cur,
            "select count(distinct race_id) from v2_odds_trifecta where race_id >= %s and race_id < %s",
            (rid_start, rid_end),
        )
        full_odds = _scalar(
            cur,
            """select count(*) from (
                    select race_id
                    from v2_odds_trifecta
                    where race_id >= %s and race_id < %s
                    group by race_id
                    having count(distinct ticket) = 120
                ) q""",
            (rid_start, rid_end),
        )

        hist_weather = 0
        if _table_exists(cur, "v2_realtime_weather_snapshots"):
            hist_weather = _scalar(
                cur,
                """select count(distinct race_id)
                   from v2_realtime_weather_snapshots
                   where race_date >= %s and race_date <= %s and snapshot_label='historical'""",
                (start, end),
            )

        hist_exh = 0
        hist_exh_full6 = 0
        if _table_exists(cur, "v2_realtime_exhibition_snapshots"):
            hist_exh = _scalar(
                cur,
                """select count(distinct race_id)
                   from v2_realtime_exhibition_snapshots
                   where race_date >= %s and race_date <= %s and snapshot_label='historical'""",
                (start, end),
            )
            exh_lane_col = next(
                (
                    c
                    for c in ("lane", "course", "boat_no")
                    if _column_exists(cur, "v2_realtime_exhibition_snapshots", c)
                ),
                None,
            )
            if exh_lane_col:
                hist_exh_full6 = _scalar(
                    cur,
                    f"""select count(*) from (
                            select race_id
                            from v2_realtime_exhibition_snapshots
                            where race_date >= %s and race_date <= %s
                              and snapshot_label='historical'
                            group by race_id
                            having count(distinct {exh_lane_col}) = 6
                        ) q""",
                    (start, end),
                )

    return MonthReadiness(
        month=start.strftime("%Y-%m"),
        start_date=start,
        end_date=end,
        race_count=races,
        result_races=results,
        full_result_entry_races=full_results,
        base_odds_races=base_odds,
        full_120_base_odds_races=full_odds,
        historical_weather_races=hist_weather,
        historical_exhibition_races=hist_exh,
        historical_exhibition_full6_races=hist_exh_full6,
    )


def audit_candidates(
    conn: Any,
    *,
    today: date | None = None,
    lookback_months: int = DEFAULT_LOOKBACK_MONTHS,
    min_age_days: int = DEFAULT_MIN_AGE_DAYS,
) -> list[MonthReadiness]:
    today = today or datetime.now(JST).date()
    rows = [
        audit_month(conn, start, end)
        for start, end in candidate_months(
            today=today,
            lookback_months=lookback_months,
            min_age_days=min_age_days,
        )
    ]
    return sorted(rows, key=lambda r: (r.pilot_score, r.month), reverse=True)


def main() -> None:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is required")
    lookback = int(os.getenv("ARCHIVE_PILOT_LOOKBACK_MONTHS", str(DEFAULT_LOOKBACK_MONTHS)))
    min_age = int(os.getenv("ARCHIVE_PILOT_MIN_AGE_DAYS", str(DEFAULT_MIN_AGE_DAYS)))

    import psycopg

    with psycopg.connect(
        dsn,
        options="-c default_transaction_read_only=on -c statement_timeout=120000 -c timezone=UTC",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("show transaction_read_only")
            if str(cur.fetchone()[0]).lower() != "on":
                raise RuntimeError("read-only guard failed")
        rows = audit_candidates(conn, lookback_months=lookback, min_age_days=min_age)

    print("ARCHIVE_PILOT_READINESS=READ_ONLY", flush=True)
    for row in rows:
        print(
            f"month={row.month} settled={str(row.settled).lower()} "
            f"races={row.race_count} results={row.result_races} "
            f"result_full6={row.full_result_entry_races} "
            f"base_odds={row.base_odds_races} base_odds_full120={row.full_120_base_odds_races} "
            f"historical_weather={row.historical_weather_races} "
            f"historical_exhibition={row.historical_exhibition_races} "
            f"historical_exhibition_full6={row.historical_exhibition_full6_races}",
            flush=True,
        )


if __name__ == "__main__":
    main()
