# -*- coding: utf-8 -*-
from utils.time_utils import today_str
from app.jobs.morning_summary_job import run_morning_summary_job


def main():
    target_date = today_str()
    print("MORNING SUMMARY DATE:", target_date)
    run_morning_summary_job(target_date)


if __name__ == "__main__":
    main()