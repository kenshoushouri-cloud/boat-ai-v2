# -*- coding: utf-8 -*-

“””
結果データ修復スクリプト
以下の2つをまとめて実行します:

【1】欠損チェック&再取得

- 期間内の全race_idを生成してv2_resultsと比較
- 欠損しているrace_idを再スクレイピング
- 取得成功 → 保存
- 本当にデータなし → result_status=“no_race” で記録

【2】払戻0円の修正

- v2_resultsのtrifecta_payout_yen=0のレコードを再スクレイピング
- 正しい払戻金額で上書き保存

実行タイミング:バックフィル完了後に実行してください
“””

import os
import sys
import time
import urllib.parse
import requests as http_requests
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(**file**))

from config.settings import SUPABASE_URL, SUPABASE_KEY
from db.client import upsert
from data_pipeline.fetch_results import (
_fetch_race_result_html,
_parse_race_result,
parse_result_row,
)

TARGET_VENUES = [“01”, “06”, “12”, “18”, “24”]
RACE_NUMBERS = list(range(1, 13))

HEADERS = {
“apikey”: SUPABASE_KEY,
“Authorization”: f”Bearer {SUPABASE_KEY}”,
“Content-Type”: “application/json”,
}

# ============================================================

# 共通ユーティリティ

# ============================================================

def daterange(start_date, end_date):
cur = start_date
while cur <= end_date:
yield cur
cur += timedelta(days=1)

def scrape_and_save(hd, race_date, venue, rno, record_no_race=True):
“””
1レースをスクレイピングしてv2_resultsに保存する。
戻り値: “ok” | “no_race” | “failed”
“””
race_id = f”{hd}*{venue}*{rno:02d}”
html, url = _fetch_race_result_html(hd, venue, rno)

```
if not html:
    print(f"    ❌ fetch失敗: {race_id}")
    return "failed"

row = _parse_race_result(html, race_date, venue, rno)

if row is None:
    print(f"    ⬜ データなし確認: {race_id}")
    if record_no_race:
        upsert("v2_results", {
            "race_id": race_id,
            "result_status": "no_race",
            "source": "repair_script",
        }, on_conflict="race_id")
    return "no_race"

parsed = parse_result_row(row)
if parsed:
    upsert("v2_results", parsed, on_conflict="race_id")
    print(
        f"    ✅ 保存: {race_id}"
        f" 3連単={parsed.get('trifecta_ticket')} {parsed.get('trifecta_payout_yen')}円"
    )
    return "ok"
else:
    print(f"    ❌ parseエラー: {race_id}")
    return "failed"
```

# ============================================================

# 【1】欠損チェック&再取得

# ============================================================

def get_existing_race_ids_for_date(hd):
prefix_start = f”{hd}_”
prefix_end = f”{hd}`"  # '_'(95)の次のASCII文字'`’(96)で範囲終端

```
url = (
    f"{SUPABASE_URL}/rest/v1/v2_results"
    f"?select=race_id"
    f"&race_id=gte.{urllib.parse.quote(prefix_start)}"
    f"&race_id=lt.{urllib.parse.quote(prefix_end)}"
    f"&limit=1000"
)
try:
    res = http_requests.get(url, headers=HEADERS, timeout=15)
    if not res.ok:
        print(f"❌ get_existing失敗: {res.status_code} {res.text}")
        return set()
    return {row["race_id"] for row in res.json()}
except Exception as e:
    print(f"❌ get_existing例外: {e}")
    return set()
```

def run_missing_check(start_date_str, end_date_str, sleep_sec=0.5, record_no_race=True):
print(”\n” + “=” * 50)
print(”【1】欠損チェック&再取得”)
print(“期間:”, start_date_str, “→”, end_date_str)
print(”=” * 50)

```
start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

total_ok = []
total_no_race = []
total_failed = []

for d in daterange(start_date, end_date):
    hd = d.strftime("%Y%m%d")
    race_date = d.strftime("%Y-%m-%d")

    # 期待されるrace_id一覧
    expected = {
        f"{hd}_{v}_{r:02d}": (v, r)
        for v in TARGET_VENUES
        for r in RACE_NUMBERS
    }
    existing = get_existing_race_ids_for_date(hd)
    missing = {
        race_id: vr
        for race_id, vr in expected.items()
        if race_id not in existing
    }

    if not missing:
        print(f"  ✅ {race_date} 欠損なし")
        continue

    print(f"\n  ⚠️  {race_date} 欠損={len(missing)}件")
    for race_id in sorted(missing.keys()):
        print(f"    - {race_id}")

    for race_id, (venue, rno) in sorted(missing.items()):
        result = scrape_and_save(hd, race_date, venue, rno, record_no_race)
        if result == "ok":
            total_ok.append(race_id)
        elif result == "no_race":
            total_no_race.append(race_id)
        else:
            total_failed.append(race_id)
        time.sleep(sleep_sec)

print("\n--- 欠損チェック結果 ---")
print(f"復元成功:     {len(total_ok)}件")
print(f"開催なし確認: {len(total_no_race)}件")
print(f"再取得失敗:   {len(total_failed)}件")
if total_failed:
    print("失敗race_id:")
    for r in sorted(total_failed):
        print(" ", r)
```

# ============================================================

# 【2】払戻0円の修正

# ============================================================

def get_zero_payout_race_ids():
“”“trifecta_payout_yen=0 かつ result_status=‘official’ のrace_idを取得”””
url = (
f”{SUPABASE_URL}/rest/v1/v2_results”
f”?select=race_id”
f”&trifecta_payout_yen=eq.0”
f”&result_status=eq.official”
f”&limit=10000”
)
try:
res = http_requests.get(url, headers=HEADERS, timeout=15)
if not res.ok:
print(f”❌ get_zero_payout失敗: {res.status_code} {res.text}”)
return []
return [row[“race_id”] for row in res.json()]
except Exception as e:
print(f”❌ get_zero_payout例外: {e}”)
return []

def run_zero_payout_fix(sleep_sec=0.5):
print(”\n” + “=” * 50)
print(”【2】払戻0円の修正”)
print(”=” * 50)

```
race_ids = get_zero_payout_race_ids()
print(f"対象件数: {len(race_ids)}件")

if not race_ids:
    print("✅ 払戻0円のレコードなし")
    return

ok = []
failed = []

for race_id in sorted(race_ids):
    # race_idからhd・venue・rnoを分解
    # 形式: 20260211_06_01
    parts = race_id.split("_")
    if len(parts) != 3:
        print(f"    ❌ race_id形式エラー: {race_id}")
        failed.append(race_id)
        continue

    hd, venue, rno_str = parts
    rno = int(rno_str)
    race_date = f"{hd[:4]}-{hd[4:6]}-{hd[6:8]}"

    result = scrape_and_save(hd, race_date, venue, rno, record_no_race=False)
    if result == "ok":
        ok.append(race_id)
    else:
        failed.append(race_id)
    time.sleep(sleep_sec)

print("\n--- 払戻修正結果 ---")
print(f"修正成功: {len(ok)}件")
print(f"失敗:     {len(failed)}件")
if failed:
    print("失敗race_id:")
    for r in sorted(failed):
        print(" ", r)
```

# ============================================================

# メイン

# ============================================================

def main():
START_DATE = “2025 6-01-01”
END_DATE = “2026-04-22”
SLEEP_SEC = 0.5

```
# 【1】欠損チェック&再取得
run_missing_check(
    start_date_str=START_DATE,
    end_date_str=END_DATE,
    sleep_sec=SLEEP_SEC,
    record_no_race=True,
)

# 【2】払戻0円の修正
run_zero_payout_fix(sleep_sec=SLEEP_SEC)

print("\n🎉 全修復処理完了!")
```

if **name** == “**main**”:
main()
