# -*- coding: utf-8 -*-
import os
import sys

sys.path.append(os.path.dirname(__file__))

# Pythonista ローカル実行用
os.environ["SUPABASE_URL"] = "https://dpctymeddnggfolvvcyf.supabase.co"
os.environ["SUPABASE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRwY3R5bWVkZG5nZ2ZvbHZ2Y3lmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjUzNjE1OSwiZXhwIjoyMDkyMTEyMTU5fQ.4ifEIF0LIKqgPOm5jpl7PbXMSflD_IOlBzMlfoQMyzs"

from app.jobs.race_seed_job import run_race_seed_job
from utils.time_utils import today_str

def main():
    run_race_seed_job(today_str())

if __name__ == "__main__":
    main()
