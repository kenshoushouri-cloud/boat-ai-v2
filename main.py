# -*- coding: utf-8 -*-
import os

from run_report import main as report_main
from run_results import main as results_main
from run_morning_jobs import main as morning_main
from run_pre_race_jobs import main as prerace_main
from run_seed import main as seed_main
from run_odds import main as odds_main


def main():
    job_mode = os.environ.get("JOB_MODE", "").strip().lower()
    print("JOB_MODE:", job_mode)

    if job_mode == "report":
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
    else:
        print("JOB_MODE未設定 → 終了")
        print("有効なJOB_MODE: report / results / morning / prerace / seed / odds")


if __name__ == "__main__":
    main()