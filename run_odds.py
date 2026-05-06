# -*- coding: utf-8 -*-
from app.jobs.odds_seed_job import run_odds_seed_job
from utils.time_utils import today_str

def main():
    # 本番用：当日の対象レースを全て取得
    run_odds_seed_job(today_str(), limit_races=None)

if __name__ == "__main__":
    main()