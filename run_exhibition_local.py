# -*- coding: utf-8 -*-
import os
import sys

sys.path.append(os.path.dirname(__file__))

os.environ["SUPABASE_URL"] = "https://dpctymeddnggfolvvcyf.supabase.co"
os.environ["SUPABASE_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRwY3R5bWVkZG5nZ2ZvbHZ2Y3lmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjUzNjE1OSwiZXhwIjoyMDkyMTEyMTU5fQ.4ifEIF0LIKqgPOm5jpl7PbXMSflD_IOlBzMlfoQMyzs"

from app.jobs.exhibition_seed_job import run_exhibition_seed_job


def main():
    target_date = "2026-04-20"
    print("EXHIBITION TARGET DATE:", target_date)
    run_exhibition_seed_job(target_date)


if __name__ == "__main__":
    main()
