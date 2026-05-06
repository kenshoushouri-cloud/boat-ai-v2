# -*- coding: utf-8 -*-
import os
import time

from run_report import main as report_main
from run_results import main as results_main
from run_morning_jobs import main as morning_main
from run_pre_race_jobs import main as prerace_main
from run_seed import main as seed_main
from run_odds import main as odds_main


def main():
    job_mode = os.environ.get("JOB_MODE", "idle").strip().lower()

    print("JOB_MODE:", job_mode)
    print("JOB_MODE repr:", repr(job_mode))

    if job_mode in ("", "idle"):
        print("JOB_MODE未設定またはidle → 待機モード")
        print("バックテストは実行しません。")
        while True:
            print("boat_ai_v2 idle...")
            time.sleep(3600)

    elif job_mode == "report":
        report_main()

    elif job_mode == "results":
        results_main()

    elif job_mode == "morning":
        morning_main()

    elif job_mode == "prerace":
        prerace_main()

    elif job_mode == "seed":
        seed_main()

    elif job_mode == "odds":
        odds_main()

    elif job_mode == "backfill_other":
        from scripts.run_backfill_other_venues import main as backfill_other_main
        backfill_other_main()

    else:
        print(f"不明なJOB_MODE: {job_mode}")
        print(
            "有効なJOB_MODE: "
            "idle / report / results / morning / prerace / seed / odds / backfill_other"
        )
        print("安全のため終了します。")


if __name__ == "__main__":
    main()