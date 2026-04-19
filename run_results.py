# -*- coding: utf-8 -*-
from app.jobs.result_fetch_job import run_result_fetch_job
from utils.time_utils import yesterday_str

def main():
    run_result_fetch_job(yesterday_str())

if __name__ == "__main__":
    main()
