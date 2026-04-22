# -*- coding: utf-8 -*-
import requests
from db.client import insert

BASE_URL = "https://boatraceopenapi.github.io"


def fetch_exhibition(date_yyyymmdd):
    year = date_yyyymmdd[:4]
    url = f"{BASE_URL}/exhibition/v2/{year}/{date_yyyymmdd}.json"
    print("EXHIBITION API:", url)

    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            print("fetch_exhibition status:", r.status_code)
            return []
        data = r.json()
        if not isinstance(data, list):
            print("fetch_exhibition invalid type:", type(data).__name__)
            return []
        return data
    except Exception as e:
        print("fetch_exhibition error:", e)
        return []


def run_backfill_exhibition(date_yyyymmdd):
    print("=== exhibition backfill start ===")
    print("target:", date_yyyymmdd)

    data = fetch_exhibition(date_yyyymmdd)
    rows = []

    for r in data:
        jcd = str(r.get("jcd", "")).zfill(2)
        rno = str(r.get("rno", "")).zfill(2)

        if not jcd or not rno:
            continue

        race_id = f"{date_yyyymmdd}_{jcd}_{rno}"

        row = {
            "race_id": race_id,
            "lane": r.get("teiban"),
            "exhibition_time": r.get("tenjiTime"),
            "start_timing": r.get("startTime"),
            "course": r.get("course"),
        }
        rows.append(row)

    print("insert target rows:", len(rows))

    if not rows:
        print("no rows")
        return

    try:
        insert("v2_exhibition", rows)
        print("insert done:", len(rows))
    except Exception as e:
        print("insert error:", e)
