# -*- coding: utf-8 -*-
import os
import sys

sys.path.append(os.path.dirname(__file__))

from app.jobs.result_fetch_job import run_result_fetch_job

def main():
    run_result_fetch_job("2026-04-20", debug_first_n=3)

if __name__ == "__main__":
    main()
