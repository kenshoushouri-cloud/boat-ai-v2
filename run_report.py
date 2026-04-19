# -*- coding: utf-8 -*-
from app.jobs.daily_report_job import run_daily_report_job
from utils.time_utils import yesterday_str

def main():
    run_daily_report_job(yesterday_str())

if __name__ == "__main__":
    main()
