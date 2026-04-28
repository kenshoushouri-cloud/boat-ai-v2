# -*- coding: utf-8 -*-
import os
import sys
import time
import urllib.parse
import requests as http_requests
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(__file__))

from config.settings import SUPABASE_URL, SUPABASE_KEY
from db.client import upsert
from data_pipeline.fetch_programs import (
    _fetch_racelist_html,
    _parse_racelist,
    parse_entry_rows,
)

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def get_null_entry_race_ids():
    """national_win_rate が NULL の race_id 一覧を取得"""
    url = (
        f"{SUPABASE_URL}/rest/v1/v2_race_entries"
        f"?select=race_id"
        f"&national_win_rate=is.null"
        f"&limit=10000"
    )
    try:
        res = http_requests.get(url, headers=HEADERS, timeout=15)
        if not res.ok:
            print(f"❌ 取得失敗: {res.status_code} {res.text}")
            return []
        # race_id の重複を除去
        seen = set()
        result = []
        for row in res.json():
            rid = row["race_id"]
            if rid not in seen:
                seen.add(rid)
                result.append(rid)
        return result
    except Exception as e:
        print(f"❌ 例外: {e}")
        return []


def refetch_entries_for_race(race_id):
    """
    race_id から hd・venue・rno を分解して出走表を再取得し upsert する
    race_id 形式: 20250919_06_01
    """
    parts = race_id.split("_")
    if len(parts) != 3:
        print(f"  ❌ race_id形式エラー: {race_id}")
        return False

    hd, venue, rno_str = parts
    rno = int(rno_str)
    target_date = f"{hd[:4]}-{hd[4:6]}-{hd[6:8]}"

    html, url = _fetch_racelist_html(hd, venue, rno)
    if not html:
        print(f"  ❌ fetch失敗: {race_id}")
        return False

    row = _parse_racelist(html, hd, venue, rno)
    if not row:
        print(f"  ⬜ データなし: {race_id}")
        return False

    entries = parse_entry_rows(row, target_date)
    for entry in entries:
        upsert("v2_race_entries", entry, on_conflict=["race_id", "lane"])

    print(
        f"  ✅ 更新: {race_id} "
        f"({len(entries)}艇 "
        f"motor={entries[0].get('motor_no')}/{entries[0].get('motor_place2_rate')} "
        f"nat={entries[0].get('national_win_rate')})"
    )
    return True


def run_entry_repair(sleep_sec=0.5):
    print("=== 出走表NULLデータ修復 開始 ===")

    race_ids = get_null_entry_race_ids()
    print(f"対象race_id数: {len(race_ids)}件")

    if not race_ids:
        print("✅ NULLデータなし")
        return

    ok = []
    failed = []

    for race_id in sorted(race_ids):
        result = refetch_entries_for_race(race_id)
        if result:
            ok.append(race_id)
        else:
            failed.append(race_id)
        time.sleep(sleep_sec)

    print("\n=== 出走表NULLデータ修復 終了 ===")
    print(f"更新成功: {len(ok)}件")
    print(f"失敗:     {len(failed)}件")
    if failed:
        print("失敗race_id:")
        for r in sorted(failed):
            print(" ", r)


def main():
    run_entry_repair(sleep_sec=0.5)
    print("\n完了！")


if __name__ == "__main__":
    main()
    while True:
        time.sleep(3600)