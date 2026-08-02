# -*- coding: utf-8 -*-
"""
run_historical_month_backfill_pg.py

過去1か月分のレース情報・出走表・結果・三連単オッズを
repair_month_all_pg.py で補修し、完了後に品質監査を行います。

目的:
- 場別・一般戦・グレード戦・オールレディース等のバックテスト母数を増やす
- 1か月ずつ安全に遡る
- 取得後に完全オッズ件数、結果件数、レース名欠損を確認する

重要:
- LINE通知・本番判定・購入処理はありません。
- DBは更新します。
- 初回は必ずテスト用Serviceで1か月だけ実行してください。

Start Command:
    python -u run_historical_month_backfill_pg.py

必須Variables:
    DATABASE_URL
    HISTORICAL_BACKFILL_MONTH=2026-05

任意Variables:
    HISTORICAL_BACKFILL_DO_RACES=1
    HISTORICAL_BACKFILL_DO_RESULTS=1
    HISTORICAL_BACKFILL_DO_ODDS=1
    HISTORICAL_BACKFILL_ODDS_IS_FINAL=1
    HISTORICAL_BACKFILL_WORKERS=4
    HISTORICAL_BACKFILL_ODDS_WORKERS=2
    HISTORICAL_BACKFILL_SLEEP_SEC=0.1
    HISTORICAL_BACKFILL_STRICT_AUDIT=1
    HISTORICAL_BACKFILL_MIN_COMPLETE_RATE_PCT=90
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all, fetch_one

JST = timezone(timedelta(hours=9))

TARGET_MONTH = os.getenv("HISTORICAL_BACKFILL_MONTH", "2026-05").strip()

DO_RACES = os.getenv(
    "HISTORICAL_BACKFILL_DO_RACES", "1"
).strip().lower() in {"1", "true", "yes", "on"}

DO_RESULTS = os.getenv(
    "HISTORICAL_BACKFILL_DO_RESULTS", "1"
).strip().lower() in {"1", "true", "yes", "on"}

DO_ODDS = os.getenv(
    "HISTORICAL_BACKFILL_DO_ODDS", "1"
).strip().lower() in {"1", "true", "yes", "on"}

ODDS_IS_FINAL = os.getenv(
    "HISTORICAL_BACKFILL_ODDS_IS_FINAL", "1"
).strip().lower() in {"1", "true", "yes", "on"}

WORKERS = int(os.getenv("HISTORICAL_BACKFILL_WORKERS", "4"))
ODDS_WORKERS = int(os.getenv("HISTORICAL_BACKFILL_ODDS_WORKERS", "2"))
SLEEP_SEC = float(os.getenv("HISTORICAL_BACKFILL_SLEEP_SEC", "0.1"))

STRICT_AUDIT = os.getenv(
    "HISTORICAL_BACKFILL_STRICT_AUDIT", "1"
).strip().lower() in {"1", "true", "yes", "on"}

MIN_COMPLETE_RATE_PCT = float(
    os.getenv("HISTORICAL_BACKFILL_MIN_COMPLETE_RATE_PCT", "90")
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def _month_bounds(ym: str) -> Tuple[str, str, str]:
    try:
        dt = datetime.strptime(ym, "%Y-%m")
    except ValueError as exc:
        raise RuntimeError(
            "HISTORICAL_BACKFILL_MONTHはYYYY-MM形式で指定してください。"
        ) from exc

    last_day = monthrange(dt.year, dt.month)[1]
    start = f"{dt.year:04d}-{dt.month:02d}-01"
    end = f"{dt.year:04d}-{dt.month:02d}-{last_day:02d}"

    if dt.month == 12:
        next_start = f"{dt.year + 1:04d}-01-01"
    else:
        next_start = f"{dt.year:04d}-{dt.month + 1:02d}-01"

    return start, end, next_start


def _run_repair(
    script_path: Path,
    start_date: str,
    end_date: str,
) -> None:
    env = os.environ.copy()
    env.update(
        {
            "REPAIR_START_DATE": start_date,
            "REPAIR_END_DATE": end_date,
            "REPAIR_DO_RACES": "1" if DO_RACES else "0",
            "REPAIR_DO_RESULTS": "1" if DO_RESULTS else "0",
            "REPAIR_DO_ODDS": "1" if DO_ODDS else "0",
            "ODDS_IS_FINAL": "1" if ODDS_IS_FINAL else "0",
            "REPAIR_WORKERS": str(WORKERS),
            "REPAIR_ODDS_WORKERS": str(ODDS_WORKERS),
            "REPAIR_SLEEP_SEC": str(SLEEP_SEC),
            "PYTHONUNBUFFERED": "1",
        }
    )

    print("=" * 80, flush=True)
    print("HISTORICAL MONTH BACKFILL START", flush=True)
    print(f"SCRIPT={script_path.name}", flush=True)
    print(f"PERIOD={start_date}..{end_date}", flush=True)
    print(
        f"DO_RACES={DO_RACES} DO_RESULTS={DO_RESULTS} "
        f"DO_ODDS={DO_ODDS} ODDS_IS_FINAL={ODDS_IS_FINAL}",
        flush=True,
    )
    print(
        f"WORKERS={WORKERS} ODDS_WORKERS={ODDS_WORKERS} "
        f"SLEEP_SEC={SLEEP_SEC}",
        flush=True,
    )
    print("=" * 80, flush=True)

    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-u", str(script_path)],
        cwd=str(script_path.parent),
        env=env,
        text=True,
        check=False,
    )
    elapsed = time.monotonic() - started

    print("=" * 80, flush=True)
    print(
        f"HISTORICAL MONTH BACKFILL END "
        f"returncode={result.returncode} elapsed={elapsed:.1f}s",
        flush=True,
    )
    print("=" * 80, flush=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"repair_month_all_pg.py が失敗しました。"
            f"returncode={result.returncode}"
        )


def _audit_month(
    start_date: str,
    next_start: str,
) -> Dict[str, Any]:
    race_row = fetch_one(
        """
        select
            count(*) as races,
            count(*) filter (
                where race_name is null or btrim(race_name) = ''
            ) as race_name_missing,
            count(distinct race_date) as active_days
        from v2_races
        where race_date >= %s
          and race_date < %s;
        """,
        (start_date, next_start),
    ) or {}

    entries_row = fetch_one(
        """
        select
            count(*) as entry_rows,
            count(distinct race_id) as entry_races
        from v2_race_entries
        where race_id >= %s
          and race_id < %s;
        """,
        (start_date.replace("-", ""), next_start.replace("-", "")),
    ) or {}

    result_row = fetch_one(
        """
        select
            count(*) as result_rows,
            count(*) filter (
                where trifecta_ticket is not null
                  and trifecta_payout_yen > 0
            ) as valid_results,
            count(*) filter (
                where result_status = 'parse_error'
                   or race_status = 'parse_error'
            ) as parse_errors
        from v2_results
        where race_id >= %s
          and race_id < %s;
        """,
        (start_date.replace("-", ""), next_start.replace("-", "")),
    ) or {}

    odds_counts = fetch_all(
        """
        select
            race_id,
            count(distinct ticket) as ticket_count,
            bool_or(coalesce(is_final, false)) as any_final
        from v2_odds_trifecta
        where race_id >= %s
          and race_id < %s
        group by race_id;
        """,
        (start_date.replace("-", ""), next_start.replace("-", "")),
    )

    complete_120 = 0
    complete_60 = 0
    complete_24 = 0
    partial = 0
    final_races = 0

    for row in odds_counts:
        count = _safe_int(row.get("ticket_count"), 0)
        if count == 120:
            complete_120 += 1
        elif count == 60:
            complete_60 += 1
        elif count == 24:
            complete_24 += 1
        elif count > 0:
            partial += 1

        if bool(row.get("any_final")):
            final_races += 1

    category_rows = fetch_all(
        """
        select
            case
                when race_name ilike '%%オールレディース%%'
                  then 'all_ladies'
                when race_name ilike '%%ヴィーナス%%'
                  or race_name ilike '%%ビーナス%%'
                  then 'venus'
                when race_name ilike '%%レディース%%'
                  or race_name ilike '%%女子%%'
                  then 'ladies_other'
                when upper(race_name) like '%%SG%%'
                  then 'SG_like'
                when upper(race_name) like '%%G1%%'
                  or race_name like '%%GⅠ%%'
                  or race_name ilike '%%周年%%'
                  or race_name ilike '%%開設%%'
                  then 'G1_like'
                when upper(race_name) like '%%G2%%'
                  or race_name like '%%GⅡ%%'
                  then 'G2_like'
                when upper(race_name) like '%%G3%%'
                  or race_name like '%%GⅢ%%'
                  or race_name ilike '%%企業杯%%'
                  then 'G3_like'
                when race_name ilike '%%ルーキー%%'
                  then 'rookie'
                when race_name ilike '%%マスターズ%%'
                  or race_name ilike '%%名人%%'
                  then 'masters'
                when race_name ilike '%%一般%%'
                  then 'general_named'
                when race_name is null or btrim(race_name) = ''
                  then 'name_missing'
                else 'category_other'
            end as category,
            count(*) as races
        from v2_races
        where race_date >= %s
          and race_date < %s
        group by 1
        order by races desc, category;
        """,
        (start_date, next_start),
    )

    races = _safe_int(race_row.get("races"), 0)
    complete_total = complete_120 + complete_60 + complete_24
    complete_rate = (
        complete_total / races * 100.0 if races > 0 else 0.0
    )

    return {
        "races": races,
        "active_days": _safe_int(race_row.get("active_days"), 0),
        "race_name_missing": _safe_int(
            race_row.get("race_name_missing"), 0
        ),
        "entry_rows": _safe_int(entries_row.get("entry_rows"), 0),
        "entry_races": _safe_int(entries_row.get("entry_races"), 0),
        "result_rows": _safe_int(result_row.get("result_rows"), 0),
        "valid_results": _safe_int(result_row.get("valid_results"), 0),
        "parse_errors": _safe_int(result_row.get("parse_errors"), 0),
        "odds_races": len(odds_counts),
        "complete_120": complete_120,
        "complete_60": complete_60,
        "complete_24": complete_24,
        "complete_total": complete_total,
        "partial": partial,
        "final_races": final_races,
        "complete_rate": complete_rate,
        "categories": category_rows,
    }


def _print_audit(audit: Dict[str, Any]) -> None:
    print("", flush=True)
    print("=== historical month audit ===", flush=True)
    print(
        f"races={audit['races']} "
        f"active_days={audit['active_days']} "
        f"race_name_missing={audit['race_name_missing']}",
        flush=True,
    )
    print(
        f"entry_rows={audit['entry_rows']} "
        f"entry_races={audit['entry_races']}",
        flush=True,
    )
    print(
        f"result_rows={audit['result_rows']} "
        f"valid_results={audit['valid_results']} "
        f"parse_errors={audit['parse_errors']}",
        flush=True,
    )
    print(
        f"odds_races={audit['odds_races']} "
        f"complete120={audit['complete_120']} "
        f"complete60={audit['complete_60']} "
        f"complete24={audit['complete_24']} "
        f"partial={audit['partial']} "
        f"final_races={audit['final_races']} "
        f"complete_rate={audit['complete_rate']:.2f}%",
        flush=True,
    )

    print("=== category preview ===", flush=True)
    for row in audit["categories"]:
        print(
            f"{row.get('category')}: races={row.get('races')}",
            flush=True,
        )


def _validate_audit(audit: Dict[str, Any]) -> None:
    problems: List[str] = []

    if audit["races"] <= 0:
        problems.append("v2_racesが0件")

    if DO_RACES and audit["entry_races"] < audit["races"]:
        problems.append(
            f"出走表不足 entry_races={audit['entry_races']} "
            f"races={audit['races']}"
        )

    if DO_RESULTS and audit["valid_results"] <= 0:
        problems.append("有効結果が0件")

    if DO_ODDS and audit["complete_rate"] < MIN_COMPLETE_RATE_PCT:
        problems.append(
            f"完全オッズ率不足 "
            f"{audit['complete_rate']:.2f}% "
            f"< {MIN_COMPLETE_RATE_PCT:.2f}%"
        )

    if audit["parse_errors"] > 0:
        problems.append(
            f"結果parse_error={audit['parse_errors']}"
        )

    if problems:
        print("=== audit warnings ===", flush=True)
        for problem in problems:
            print(f"⚠️ {problem}", flush=True)

        if STRICT_AUDIT:
            raise RuntimeError(
                "品質監査に未達項目があります: "
                + "; ".join(problems)
            )
    else:
        print("AUDIT=PASS", flush=True)


def main() -> None:
    print(
        "✅ run_historical_month_backfill_pg.py "
        "VERSION 2026-08-03 month-backfill-audit-v1",
        flush=True,
    )

    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    start_date, end_date, next_start = _month_bounds(TARGET_MONTH)

    base_dir = Path(__file__).resolve().parent
    repair_script = base_dir / "repair_month_all_pg.py"

    if not repair_script.exists():
        raise FileNotFoundError(
            f"repair_month_all_pg.py が見つかりません: "
            f"{repair_script}"
        )

    _run_repair(
        script_path=repair_script,
        start_date=start_date,
        end_date=end_date,
    )

    audit = _audit_month(start_date, next_start)
    _print_audit(audit)
    _validate_audit(audit)

    print(
        "=== historical month backfill + audit completed ===",
        flush=True,
    )


if __name__ == "__main__":
    main()