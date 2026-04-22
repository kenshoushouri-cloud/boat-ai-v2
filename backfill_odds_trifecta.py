# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
from db.client import upsert

BOATS = {"1", "2", "3", "4", "5", "6"}
TARGET_VENUES = ["01", "06", "12", "18", "24"]


def fetch_odds_html(jcd, rno, date_yyyymmdd):
    url = (
        f"https://www.boatrace.jp/owpc/pc/race/odds3t"
        f"?rno={int(rno)}&jcd={str(jcd).zfill(2)}&hd={date_yyyymmdd}"
    )
    print("ODDS URL:", url)

    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.boatrace.jp/",
            },
            timeout=15,
        )
        print("HTTP STATUS:", r.status_code)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        print("HTML LENGTH:", len(r.text))
        return r.text
    except Exception as e:
        print("fetch_odds_html error:", e)
        return None


def _is_odds(s):
    try:
        float(str(s).replace(",", ""))
        return True
    except Exception:
        return False


def parse_odds_rows(html):
    print("parse start")
    soup = BeautifulSoup(html, "html.parser")
    trs = soup.find_all("tr")
    print("TR COUNT:", len(trs))

    rows = []
    current_first = None

    for tr_idx, tr in enumerate(trs):
        # 1着艇を th から保持
        for th in tr.find_all("th"):
            head = th.get_text(strip=True)
            if head in BOATS:
                current_first = head
                break

        texts = [td.get_text(strip=True) for td in tr.find_all("td")]

        if tr_idx < 10:
            print(f"ROW {tr_idx}: first={current_first}, texts={texts[:12]}")

        if not texts or not current_first:
            continue

        # [2艇目, 3艇目, オッズ] の繰り返しを読む
        i = 0
        while i + 2 < len(texts):
            second = texts[i]
            third = texts[i + 1]
            odds_text = texts[i + 2]

            if (
                second in BOATS
                and third in BOATS
                and _is_odds(odds_text)
                and len({current_first, second, third}) == 3
            ):
                ticket = f"{current_first}-{second}-{third}"
                rows.append({
                    "ticket": ticket,
                    "odds": float(str(odds_text).replace(",", "")),
                })
                i += 3
            else:
                i += 1

    # 重複除去
    dedup = {}
    for row in rows:
        dedup[row["ticket"]] = row

    result = list(dedup.values())
    result.sort(key=lambda x: x["ticket"])

    print(f"parsed odds rows: {len(result)}")
    if result[:10]:
        print("SAMPLE:", result[:10])

    return result


def save_odds_rows(race_id, odds_rows):
    print(f"save start: {race_id}, rows={len(odds_rows)}")

    rows_to_upsert = [
        {
            "race_id": race_id,
            "ticket": row["ticket"],
            "odds": row["odds"],
        }
        for row in odds_rows
    ]

    try:
        result = upsert(
            "v2_odds_trifecta",
            rows_to_upsert,
            on_conflict="race_id,ticket"
        )
        if result is not None:
            print(f"saved odds rows: {race_id} {len(rows_to_upsert)}")
            return len(rows_to_upsert)

        print(f"upsert failed: {race_id}")
        return 0

    except Exception as e:
        print("save_odds_rows error:", race_id, e)
        return 0


def run_backfill_odds_trifecta_for_race(date_yyyymmdd, jcd, rno):
    race_id = f"{date_yyyymmdd}_{str(jcd).zfill(2)}_{str(int(rno)).zfill(2)}"
    print("=== odds backfill race start ===")
    print("race_id:", race_id)

    html = fetch_odds_html(jcd, rno, date_yyyymmdd)
    if not html:
        print("no html")
        return 0

    odds_rows = parse_odds_rows(html)
    if not odds_rows:
        print("no odds rows:", race_id)
        return 0

    saved = save_odds_rows(race_id, odds_rows)
    return saved


def run_backfill_odds_trifecta_for_date(date_yyyymmdd):
    print("=== odds backfill date start ===")
    print("target:", date_yyyymmdd)

    saved_race_count = 0
    total_saved_rows = 0

    for jcd in TARGET_VENUES:
        for rno in range(1, 13):
            saved = run_backfill_odds_trifecta_for_race(date_yyyymmdd, jcd, rno)

            if saved > 0:
                saved_race_count += 1
                total_saved_rows += saved

    print("\n=== odds backfill date end ===")
    print("target:", date_yyyymmdd)
    print("saved_race_count:", saved_race_count)
    print("total_saved_rows:", total_saved_rows)

    return {
        "date": date_yyyymmdd,
        "saved_race_count": saved_race_count,
        "total_saved_rows": total_saved_rows,
    }


if __name__ == "__main__":
    # まずは1日分テスト
    run_backfill_odds_trifecta_for_date("20260420")
