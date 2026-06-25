# -*- coding: utf-8 -*-
import os
import runpy
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
os.environ.setdefault("TARGET_DATE", datetime.now(JST).strftime("%Y-%m-%d"))
os.environ.setdefault("SELECTOR_MODE", "ab")
os.environ.setdefault("DECISION_LABEL_PREFIX", "final")
os.environ.setdefault("RUN_REPAIR_RESULTS", "1")
os.environ.setdefault("UNIT_YEN", "100")
runpy.run_path("v26_nightly_results_learning.py", run_name="__main__")