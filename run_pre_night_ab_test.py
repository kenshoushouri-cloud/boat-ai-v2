# -*- coding: utf-8 -*-
import os
import runpy
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
os.environ.setdefault("TARGET_DATE", datetime.now(JST).strftime("%Y-%m-%d"))
os.environ.setdefault("PRE_SESSION", "night")
os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("TEST_MODE", "1")
os.environ.setdefault("DRY_RUN", "0")
os.environ.setdefault("DAILY_LINE_LIMIT", "3")
os.environ.setdefault("MONTHLY_LINE_LIMIT", "100")
os.environ.setdefault("MAX_ITEMS_PER_MESSAGE", "6")
os.environ.setdefault("MIN_ODDS_ROWS", "100")
runpy.run_path("v24_pre_candidate_notifier_ab.py", run_name="__main__")