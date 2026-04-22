# -*- coding: utf-8 -*-

“””
欠損結果チェック＆再取得スクリプト

- 期間内の全race_id（会場×レース番号）を生成
- v2_results に存在しないrace_idを欠損候補として抽出
- 再スクレイピングして「本当にデータなし」か「取得失敗」かを判別
- 取得成功 → v2_results に保存
- 本当にデータなし → v2_results に result_status=“no_race” で記録
  “””

import os
import sys
import time
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(**file**))

from db.client import supabase  # Supabaseクライアントを直接使用
from data_pipeline.fetch_results import (
_fetch_race_result_html,
_parse_race_result,
parse_result_row,
)

TARGET_VENUES = [“01”, “06”, “12”, “18”, “24”]
RACE_NUMBERS = list(range(1, 13))

def daterange(start_date, end_date):
cur = start_date
while cur <= end_date:
yield cur
cur += timedelta(days=1)

def get_existing_race_ids_for_date(hd):
“””
race_idのプレフィックス（例: 20250322_）で v2_results を検索し
保存済みのrace_idセットを返す
“””
prefix_start = f”{hd}*”
prefix_end = f”{hd}`"  # '_'の次のASCII文字が'`’なので範囲指定に使用
res = (
supabase
.from*(“v2_results”)
.select(“race_id”)
.gte(“race_id”, prefix_start)
.lt(“race_id”, prefix_end)
.execute()
)
rows = res.data or []
return {row[“race_id”] for row in rows}

def generate_expected(hd):
“”“期待されるrace_id → (venue, rno) のdict”””
expected = {}
for venue in TARGET_VENUES:
for rno in RACE_NUMBERS:
race_id = f”{hd}*{venue}*{rno:02d}”
expected[race_id] = (venue, rno)
return expected

def refetch_missing(hd, race_date, missing_ids, sleep_sec=0.5, record_no_race=True):
recovered = []
confirmed_no_race = []
still_failed = []

```
for race_id, (venue, rno) in sorted(missing_ids.items()):
    html, url = _fetch_race_result_html(hd, venue, rno)

    if not html:
        print(f"    ❌ fetch失敗: {race_id}")
        still_failed.append(race_id)
        time.sleep(sleep_sec)
        continue

    row = _parse_race_result(html, race_date, venue, rno)

    if row is None:
        print(f"    ⬜ データなし確認: {race_id}")
        confirmed_no_race.append(race_id)

        if record_no_race:
            supabase.from_("v2_results").upsert({
                "race_id": race_id,
                "result_status": "no_race",
                "source": "missing_check",
            }, on_conflict="race_id").execute()
    else:
        parsed = parse_result_row(row)
        if parsed:
            supabase.from_("v2_results").upsert(
                parsed, on_conflict="race_id"
            ).execute()
            print(f"    ✅ 復元成功: {race_id}")
            recovered.append(race_id)
        else:
            print(f"    ❌ parseエラー: {race_id}")
            still_failed.append(race_id)

    time.sleep(sleep_sec)

return recovered, confirmed_no_race, still_failed
```

def run_missing_check(
start_date_str,
end_date_str,
sleep_sec=0.5,
record_no_race=True,
):
print(”=== 欠損チェック＆再取得 開始 ===”)
print(“期間:”, start_date_str, “→”, end_date_str)

```
start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

total_recovered = []
total_no_race = []
total_failed = []

for d in daterange(start_date, end_date):
    hd = d.strftime("%Y%m%d")
    race_date = d.strftime("%Y-%m-%d")

    expected = generate_expected(hd)
    existing = get_existing_race_ids_for_date(hd)

    missing = {
        race_id: venue_rno
        for race_id, venue_rno in expected.items()
        if race_id not in existing
    }

    if not missing:
        print(f"  ✅ {race_date} 欠損なし（{len(expected)}件）")
        continue

    print(f"\n  ⚠️  {race_date} 欠損={len(missing)}件 / 全{len(expected)}件")
    for race_id in sorted(missing.keys()):
        print(f"    - {race_id}")

    recovered, no_race, failed = refetch_missing(
        hd, race_date, missing,
        sleep_sec=sleep_sec,
        record_no_race=record_no_race,
    )
    total_recovered.extend(recovered)
    total_no_race.extend(no_race)
    total_failed.extend(failed)

print("\n=== 欠損チェック＆再取得 終了 ===")
print(f"復元成功:     {len(total_recovered)}件")
print(f"開催なし確認: {len(total_no_race)}件")
print(f"再取得失敗:   {len(total_failed)}件")

if total_failed:
    print("\n⚠️ 最終的に取得できなかったrace_id:")
    for r in sorted(total_failed):
        print(" ", r)
else:
    print("\n🎉 チェック完了！")
```

def main():
run_missing_check(
start_date_str=“2025-03-13”,
end_date_str=“2026-04-22”,
sleep_sec=0.5,
record_no_race=True,
)

if **name** == “**main**”:
main()