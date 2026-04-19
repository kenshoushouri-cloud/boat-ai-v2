# -*- coding: utf-8 -*-
from app.jobs.day_prediction_job import run_day_prediction_job
from app.jobs.night_prediction_job import run_night_prediction_job

def main():
    # テスト用
    run_day_prediction_job("2026-04-15")
    # run_night_prediction_job("2026-04-15")

if __name__ == "__main__":
    main()
