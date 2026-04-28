# -*- coding: utf-8 -*-
import os
import sys
import time
import urllib.parse
import requests as http_requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(__file__))

from config.settings import SUPABASE_URL, SUPABASE_KEY
from db.client import upsert
from data_pipeline.fetch_results import (
    _fetch_race_result_html,
    parse_result_row,
)

TARGET_VENUES = ["01", "06", "12", "18", "24"]
RACE_NUMBERS = list(range(1, 13))

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


# ============================================================
# 払戻パース（digits方式）
# ============================================================

def _parse_race_result_fixed(html, race_date, jcd, rno):
    soup = BeautifulSoup(html, "html.parser")

    no_data = soup.find(string=lambda t: t and "データがありません" in t)
    if no_data:
        print(f"    -> データがありません表示あり")
        return None

    full_text = soup.get_text(separator="\n")
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    # --- 着順パース ---
    boats = []
    seen_places = set()
    all_tables = soup.find_all("table")
    for table in all_tables:
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            try:
                place_no = int(tds[0].get_text(strip=True))
                boat_no = int(tds[1].get_text(strip=True))
                if (
                    1 <= place_no <= 6
                    and 1 <= boat_no <= 6
                    and place_no not in seen_places
                ):
                    seen_places.add(place_no)
                    boats.append({
                        "racer_place_number": place_no,
                        "racer_boat_number": boat_no,
                    })
            except Exception:
                continue

    # --- 払戻パース（digits方式: 数字以外を全て除去） ---
    payouts = {"trifecta": [], "exacta": []}

    i = 0
    while i < len(lines):
        line = lines[i]

        if line in ("3連単", "2連単"):
            kind = "trifecta" if line == "3連単" else "exacta"

            combo_parts = []
            j = i + 1
            while j < len(lines) and len(combo_parts) < 10:
                val = lines[j]
                if val in {"1", "2", "3", "4", "5", "6", "-"}:
                    combo_parts.append(val)
                    j += 1
                else:
                    break

            boat_nums = [p for p in combo_parts if p != "-"]
            if len(boat_nums) >= 2:
                combo = "-".join(boat_nums)

                payout_yen = 0
                while j < len(lines):
                    try:
                        digits = "".join(c for c in lines[j] if c.isdigit())
                        candidate = int(digits) if digits else 0
                        if candidate >= 100:
                            payout_yen = candidate
                            j += 1
                            break
                    except Exception:
                        pass
                    j += 1

                payouts[kind].append({
                    "combination": combo,
                    "payout": payout_yen,
                })

            i = j
            continue

        i += 1

    print(f"  boats={len(boats)} trifecta={payouts['trifecta'][:1]} exacta={payouts['exacta'][:1]}")

    if not boats and not payouts["trifecta"]:
        print(f"    -> パース失敗: boats=0, trifecta空 (HTML長={len(html)}文字)")
        return None

    return {
        "race_date": race_date,
        "race_stadium_number": int(jcd),
        "race_number": int(rno),
        "boats": boats,
        "payouts": payouts,
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
    race_id = f"{hd}_{venue}_{rno:02d}"
    html, url = _fetch_race_result_html(hd, venue, rno)

    if not html:
        print(f"    ❌ fetch失敗: {race_id}")
        return "failed"

    row = _parse_race_result_fixed(html, race_date, venue, rno)

    if row is None:
        print(f"    ⬜ データなし確認: {race_id}")
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


# ============================================================
# 【1】欠損チェック＆再取得
# ============================================================

def get_existing_race_ids_for_date(hd):
    prefix_start = f"{hd}_"
    prefix_end = f"{hd}`"
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


def run_missing_check(start_date_str, end_date_str, sleep_sec=0.5, record_no_race=True):
    print("\n" + "=" * 50)
    print("【1】欠損チェック＆再取得")
    print("期間:", start_date_str, "->", end_date_str)
    print("=" * 50)

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    total_ok = []
    total_no_race = []
    total_failed = []

    for d in daterange(start_date, end_date):
        hd = d.strftime("%Y%m%d")
        race_date = d.strftime("%Y-%m-%d")

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


# ============================================================
# 【2】払戻0円の修正
# ============================================================

def get_zero_payout_race_ids():
    url = (
        f"{SUPABASE_URL}/rest/v1/v2_results"
        f"?select=race_id"
        f"&trifecta_payout_yen=eq.0"
        f"&result_status=eq.official"
        f"&limit=10000"
    )
    try:
        res = http_requests.get(url, headers=HEADERS, timeout=15)
        if not res.ok:
            print(f"❌ get_zero_payout失敗: {res.status_code} {res.text}")
            return []
        return [row["race_id"] for row in res.json()]
    except Exception as e:
        print(f"❌ get_zero_payout例外: {e}")
        return []


def run_zero_payout_fix(sleep_sec=0.5):
    print("\n" + "=" * 50)
    print("【2】払戻0円の修正")
    print("=" * 50)

    race_ids = get_zero_payout_race_ids()
    print(f"対象件数: {len(race_ids)}件")

    if not race_ids:
        print("✅ 払戻0円のレコードなし")
        return

    ok = []
    failed = []

    for race_id in sorted(race_ids):
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


# ============================================================
# メイン: バックフィル → 欠損チェック → 払戻修正
# ============================================================

def main():
    from run_backfill_history import run_history_backfill

    # 2025年データのバックフィル
    run_history_backfill(
        start_date_str="2025-04-01",
        end_date_str="2026-04-27",
        sleep_sec=0.5,
        max_workers=3,
        max_retry=3,
        retry_wait_sec=10.0,
        do_race=True,
        do_exhibition=True,
        do_odds=True,
        do_results=True,
    )

    # 欠損チェック＆再取得
    run_missing_check(
        start_date_str="2025-04-01",
        end_date_str="2026-04-27",
        sleep_sec=0.5,
        record_no_race=True,
    )

    # 払戻0円の修正
    run_zero_payout_fix(sleep_sec=0.5)

    print("\n全処理完了！")


if __name__ == "__main__":
    main()
    while True:
        time.sleep(3600)