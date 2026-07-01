# -*- coding: utf-8 -*-
import os
import runpy

os.environ.setdefault("ODDS_RETENTION_DAYS", "30")
os.environ.setdefault("DRY_RUN", "0")

print("✅ run_odds_retention_cleanup.py", flush=True)
print(f"ODDS_RETENTION_DAYS={os.environ.get('ODDS_RETENTION_DAYS')}", flush=True)

runpy.run_path("v29_odds_retention_cleanup.py", run_name="__main__")