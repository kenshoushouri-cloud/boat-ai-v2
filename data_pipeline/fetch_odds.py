# -*- coding: utf-8 -*-
import re
import unicodedata
import requests
from bs4 import BeautifulSoup

ODDS_BASE_URL = "https://www.boatrace.jp/owpc/pc/race/odds3t"


def _norm(s):
    return unicodedata.normalize("NFKC", s)


def fetch_odds_page(target_date, venue_id, race_no):
    compact = target_date.replace("-", "")
    venue_id = str(venue_id).zfill(2)
    race_no = int(race_no)

    url = f"{ODDS_BASE_URL}?hd={compact}&jcd={venue_id}&rno={race_no}"
    print("ODDS URL:", url)

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.boatrace.jp/",
    }

    res = requests.get(url, headers=headers, timeout=20)
    res.raise_for_status()

    if not res.encoding or res.encoding.lower() == "iso-8859-1":
        res.encoding = res.apparent_encoding or "utf-8"

    return res.text, url


def parse_trifecta_odds(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")

    # ── テーブル検索 ──────────────────────────────────────────────────
    # 全テーブルの中から「行数が21以上 かつ ヘッダーに1〜6が揃う」ものを選ぶ
    odds_table = None
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 21:
            continue
        header_text = rows[0].get_text()
        header_nums = re.findall(r"\b([1-6])\b", header_text)
        if len(set(header_nums)) >= 6:
            odds_table = table
            break

    if not odds_table:
        # フォールバック: 行数が最も多いテーブルを使用
        all_tables = soup.find_all("table")
        if all_tables:
            odds_table = max(all_tables, key=lambda t: len(t.find_all("tr")))
            print(f"odds parser: fallback table rows={len(odds_table.find_all('tr'))}")
        else:
            print("odds parser: no table found at all")
            return {}

    all_rows = odds_table.find_all("tr")
    print(f"odds parser: table found, rows={len(all_rows)}")

    if len(all_rows) < 2:
        print("odds parser: table has no data rows")
        return {}

    # ── オッズ解析 ────────────────────────────────────────────────────
    # 構造: ヘッダー1行 + データ20行(5グループ × 4行)
    # グループ内1行目: (2着, 3着, オッズ) × 6列 = 18セル
    # グループ内2〜4行目: (3着, オッズ) × 6列 = 12セル(2着はrowspan=4で省略)
    data_rows = all_rows[1:]
    odds = {}

    def extract_nums(row):
        cells = [_norm(td.get_text(strip=True)) for td in row.find_all("td")]
        return [c for c in cells if re.match(r'^\d+(?:\.\d+)?$', c)]

    for base in range(0, len(data_rows), 4):
        group = data_rows[base:base + 4]
        if len(group) < 4:
            break

        row1_nums = extract_nums(group[0])

        if len(row1_nums) < 18:
            print(f"odds parser: group {base // 4} row1 has {len(row1_nums)} values (expected 18)")
            continue

        # 1行目: 2着艇と最初の3着+オッズを取得
        second_boats = {}
        for col in range(6):
            first  = str(col + 1)
            second = row1_nums[col * 3]
            third  = row1_nums[col * 3 + 1]
            val    = row1_nums[col * 3 + 2]
            second_boats[col] = second
            if len({first, second, third}) == 3:
                odds[f"{first}-{second}-{third}"] = float(val)

        # 2〜4行目: 残りの3着+オッズを取得
        for row in group[1:]:
            row_nums = extract_nums(row)
            if len(row_nums) < 12:
                print(f"odds parser: sub-row has {len(row_nums)} values (expected 12)")
                continue
            for col in range(6):
                first  = str(col + 1)
                second = second_boats.get(col)
                third  = row_nums[col * 2]
                val    = row_nums[col * 2 + 1]
                if second and len({first, second, third}) == 3:
                    odds[f"{first}-{second}-{third}"] = float(val)

    print(f"odds parser: {len(odds)} combinations parsed")
    return odds


def fetch_odds_for_race(target_date, venue_id, race_no):
    raw_html, source_url = fetch_odds_page(target_date, venue_id, race_no)
    odds = parse_trifecta_odds(raw_html)
    return odds, source_url
