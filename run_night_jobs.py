# -*- coding: utf-8 -*-
from app.jobs.night_prediction_job import run_night_prediction_job

def main():
    target_date = "2026-04-20"
    print("NIGHT TARGET DATE:", target_date)
    run_night_prediction_job(target_date)

if __name__ == "__main__":
    main()
