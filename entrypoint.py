# -*- coding: utf-8 -*-
import os

from run_report import main as report_main
from run_results import main as results_main
from run_day_jobs import main as day_main
from run_night_jobs import main as night_main
from main import main as single_main


def main():
    job_mode = os.environ.get("JOB_MODE", "").strip().lower()
    print("JOB_MODE:", job_mode)

    if job_mode == "report":
        report_main()
    elif job_mode == "results":
        results_main()
    elif job_mode == "day":
        day_main()
    elif job_mode == "night":
        night_main()
    else:
        print("JOB_MODE未設定のため main.py を実行")
        single_main()


if __name__ == "__main__":
    main()