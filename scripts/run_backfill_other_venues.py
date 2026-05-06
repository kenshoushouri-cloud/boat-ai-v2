# -*- coding: utf-8 -*-
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from run_backfill_history import run_history_backfill


OTHER_VENUES = [
    "02", "03", "04", "05",
    "07", "08", "09", "10", "11",
    "13", "14", "15", "16", "17",
    "19", "20", "21", "22", "23",
]


def main():
    print("=== 他場バックフィル開始 ===")
    print("対象場:", ",".join(OTHER_VENUES))

    run_history_backfill(
        start_date_str=os.environ.get("BACKFILL_START_DATE", "2025-03-13"),
        end_date_str=os.environ.get("BACKFILL_END_DATE", "2026-04-30"),
        venue_ids=OTHER_VENUES,
        sleep_sec=0.7,
        max_workers=2,
        max_retry=3,
        retry_wait_sec=15.0,
        do_race=True,
        do_exhibition=False,
        do_odds=False,
        do_results=True,
    )

    print("✅ 他場バックフィル完了")


if __name__ == "__main__":
    main()
    while True:
        time.sleep(3600)