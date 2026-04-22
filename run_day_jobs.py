# -*- coding: utf-8 -*-
from app.jobs.day_prediction_job import run_day_prediction_job

def main():
    target_date = "2026-04-20"
    print("DAY TARGET DATE:", target_date)
    run_day_prediction_job(target_date)

if __name__ == "__main__":
    main()
