# -*- coding: utf-8 -*-
from utils.time_utils import today_str
from app.jobs.pre_race_job import run_pre_race_job


def main():
    target_date = today_str()
    print("PRE RACE DATE:", target_date)
    run_pre_race_job(target_date)


if __name__ == "__main__":
    main()