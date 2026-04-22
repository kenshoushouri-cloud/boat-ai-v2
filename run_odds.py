# -*- coding: utf-8 -*-
from app.jobs.odds_seed_job import run_odds_seed_job
from utils.time_utils import today_str

def main():
    # 最初は3レースだけで十分
    run_odds_seed_job(today_str(), limit_races=3)

if __name__ == "__main__":
    main()
