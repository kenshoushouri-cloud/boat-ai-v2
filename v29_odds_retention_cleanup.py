# -*- coding: utf-8 -*-
import os
from datetime import datetime, timedelta, timezone
import requests

JST = timezone(timedelta(hours=9))
VERSION = "2026-07-02 odds-retention-cleanup-v1"

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or ""
ODDS_RETENTION_DAYS = int(os.getenv("ODDS_RETENTION_DAYS", "30"))
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "120"))

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

def require_settings():
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY/SUPABASE_KEY")
    if missing:
        raise RuntimeError("必要な環境変数が不足しています: " + ", ".join(missing))

def cutoff_key():
    cutoff_date = datetime.now(JST).date() - timedelta(days=ODDS_RETENTION_DAYS)
    return cutoff_date.strftime("%Y%m%d") + "_00_00"

def count_old_rows(cutoff):
    url = f"{SUPABASE_URL}/rest/v1/v2_odds_trifecta"
    headers = dict(HEADERS)
    headers["Prefer"] = "count=exact"
    params = [("select", "race_id"), ("race_id", f"lt.{cutoff}"), ("limit", "1")]
    r = requests.get(url, headers=headers, params=params, timeout=HTTP_TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"COUNT old odds failed {r.status_code}: {r.text[:800]}")
    cr = r.headers.get("Content-Range") or ""
    if "/" in cr:
        try:
            return int(cr.split("/", 1)[1])
        except Exception:
            return -1
    return -1

def delete_old_rows(cutoff):
    url = f"{SUPABASE_URL}/rest/v1/v2_odds_trifecta"
    headers = dict(HEADERS)
    headers["Prefer"] = "return=minimal"
    params = [("race_id", f"lt.{cutoff}")]
    if DRY_RUN:
        print(f"DRY_RUN: DELETE v2_odds_trifecta race_id < {cutoff}", flush=True)
        return 0
    r = requests.delete(url, headers=headers, params=params, timeout=HTTP_TIMEOUT)
    if r.status_code >= 400:
        raise RuntimeError(f"DELETE old odds failed {r.status_code}: {r.text[:800]}")
    return r.status_code

def main():
    print(f"✅ v29_odds_retention_cleanup.py VERSION {VERSION}", flush=True)
    require_settings()
    cutoff = cutoff_key()
    print(f"ODDS_RETENTION_DAYS={ODDS_RETENTION_DAYS} cutoff={cutoff} DRY_RUN={DRY_RUN}", flush=True)
    old_count = count_old_rows(cutoff)
    print(f"old odds rows before cleanup: {old_count}", flush=True)
    if old_count == 0:
        print("削除対象はありません。", flush=True)
        print("=== v29 odds retention cleanup 終了 ===", flush=True)
        return
    status = delete_old_rows(cutoff)
    print(f"delete status={status}", flush=True)
    print("注意: 初回大量削除後は Supabase SQL Editor で VACUUM FULL ANALYZE が必要です。", flush=True)
    print("=== v29 odds retention cleanup 終了 ===", flush=True)

if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        print("FATAL ERROR", flush=True)
        traceback.print_exc()
        raise