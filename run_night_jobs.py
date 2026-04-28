# -*- coding: utf-8 -*-
from utils.time_utils import today_str
from app.jobs.night_prediction_job import run_night_prediction_job


def main():
    target_date = today_str()
    print("NIGHT TARGET DATE:", target_date)
    run_night_prediction_job(target_date)


if __name__ == "__main__":
    main()