# -*- coding: utf-8 -*-
from app.jobs.race_seed_job import run_race_seed_job
from utils.time_utils import today_str

def main():
    run_race_seed_job(today_str())

if __name__ == "__main__":
    main()
