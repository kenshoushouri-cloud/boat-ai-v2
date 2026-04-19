# -*- coding: utf-8 -*-
from app.jobs.day_prediction_job import run_day_prediction_job
from utils.time_utils import today_str

def main():
    run_day_prediction_job(today_str())

if __name__ == "__main__":
    main()
