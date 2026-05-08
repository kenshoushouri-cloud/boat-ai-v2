# -*- coding: utf-8 -*-
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from run_backfill_history import run_history_backfill


DEFAULT_OTHER_VENUES = [
    "02", "03", "04", "05",
    "07", "08", "09", "10", "11",
    "13", "14", "15", "16", "17",
    "19", "20", "21", "22", "23",
]


def _parse_bool(value, default=False):
    if value is None:
        return default

    s = str(value).strip().lower()
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False

    return default


def _parse_int(value, default):
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _parse_float(value, default):
    try:
        return float(str(value).strip())
    except Exception:
        return default


def get_target_venues():
    """
    優先順位:
    1. BACKFILL_VENUES
    2. TARGET_VENUES
    3. DEFAULT_OTHER_VENUES
    """
    env = (
        os.environ.get("BACKFILL_VENUES")
        or os.environ.get("TARGET_VENUES")
        or ""
    ).strip()

    if env:
        return [
            v.strip().zfill(2)
            for v in env.split(",")
            if v.strip()
        ]

    return DEFAULT_OTHER_VENUES[:]


def main():
    start_date = os.environ.get("BACKFILL_START_DATE", "").strip()
    end_date = os.environ.get("BACKFILL_END_DATE", "").strip()

    if not start_date or not end_date:
        print("❌ BACKFILL_START_DATE / BACKFILL_END_DATE が未設定です")
        print("例: BACKFILL_START_DATE=2025-05-01")
        print("例: BACKFILL_END_DATE=2025-05-31")
        return

    target_venues = get_target_venues()

    max_workers = _parse_int(os.environ.get("BACKFILL_MAX_WORKERS"), 4)
    max_retry = _parse_int(os.environ.get("BACKFILL_MAX_RETRY"), 3)
    sleep_sec = _parse_float(os.environ.get("BACKFILL_SLEEP_SEC"), 0.5)
    retry_wait_sec = _parse_float(os.environ.get("BACKFILL_RETRY_WAIT_SEC"), 10.0)

    do_race = _parse_bool(os.environ.get("BACKFILL_DO_RACE"), True)
    do_exhibition = _parse_bool(os.environ.get("BACKFILL_DO_EXHIBITION"), False)
    do_odds = _parse_bool(os.environ.get("BACKFILL_DO_ODDS"), False)
    do_results = _parse_bool(os.environ.get("BACKFILL_DO_RESULTS"), True)
    skip_existing = _parse_bool(os.environ.get("BACKFILL_SKIP_EXISTING"), False)

    print("=== 他場バックフィル開始 ===")
    print("期間:", start_date, "→", end_date)
    print("対象場:", ",".join(target_venues))
    print("並列数:", max_workers)
    print("リトライ上限:", max_retry)
    print("sleep_sec:", sleep_sec)
    print("retry_wait_sec:", retry_wait_sec)
    print("do_race:", do_race)
    print("do_exhibition:", do_exhibition)
    print("do_odds:", do_odds)
    print("do_results:", do_results)
    print("skip_existing:", skip_existing)
    print("ENV BACKFILL_VENUES:", os.environ.get("BACKFILL_VENUES"))
    print("ENV TARGET_VENUES:", os.environ.get("TARGET_VENUES"))

    run_history_backfill(
        start_date_str=start_date,
        end_date_str=end_date,
        sleep_sec=sleep_sec,
        max_workers=max_workers,
        max_retry=max_retry,
        retry_wait_sec=retry_wait_sec,
        do_race=do_race,
        do_exhibition=do_exhibition,
        do_odds=do_odds,
        do_results=do_results,
        venue_ids=target_venues,
        skip_existing=skip_existing,
    )

    print("✅ 他場バックフィル完了")


if __name__ == "__main__":
    main()

    # Railwayでコンテナがすぐ落ちるのを避けたい場合用
    if _parse_bool(os.environ.get("KEEP_ALIVE_AFTER_JOB"), False):
        print("KEEP_ALIVE_AFTER_JOB=true のため待機します")
        while True:
            time.sleep(3600)