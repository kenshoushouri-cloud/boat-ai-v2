# -*- coding: utf-8 -*-
import os
import json
import time
import requests
from bs4 import BeautifulSoup

# 通常結果取得のデフォルト対象場
# venue_ids を渡さない場合だけ使う
TARGET_VENUES = ["01", "06", "12", "18", "24"]
RACE_NUMBERS = range(1, 13)


def _normalize_venues(venue_ids=None):
    """
    優先順位:
    1. 引数 venue_ids
    2. 環境変数 BACKFILL_VENUES
    3. 環境変数 TARGET_VENUES
    4. デフォルト TARGET_VENUES
    """
    if venue_ids is None:
        env_venues = (
            os.environ.get("BACKFILL_VENUES")
            or os.environ.get("TARGET_VENUES")
            or ""
        ).strip()

        if env_venues:
            venue_ids = [
                v.strip()
                for v in env_venues.split(",")
                if v.strip()
            ]
        else:
            venue_ids = TARGET_VENUES

    return [str(v).zfill(2) for v in venue_ids]


def _fetch_race_result_html(hd, jcd, rno):
    url = (
        f"https://www.boatrace.jp/owpc/pc/race/raceresult"
        f"?rno={int(rno)}&jcd={str(jcd).zfill(2)}&hd={hd}"
    )

    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://www.boatrace.jp/",
            },
            timeout=15,
        )
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text, url

    except Exception as e:
        print(f"fetch result error: jcd={jcd} rno={rno} {e}")
        return None, url


def _parse_race_result(html, race_date, jcd, rno):
    soup = BeautifulSoup(html, "html.parser")

    no_data = soup.find(string=lambda t: t and "データがありません" in t)
    if no_data:
        print("    → 「データがありません」表示あり")
        return None

    full_text = soup.get_text(separator="\n")
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    # 着順パース
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

    # 払戻パース
    payouts = {
        "trifecta": [],
        "exacta": [],
    }

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

    print(
        f"  boats={len(boats)}"
        f" trifecta={payouts['trifecta'][:1]}"
        f" exacta={payouts['exacta'][:1]}"
    )

    if not boats and not payouts["trifecta"]:
        print(
            f"    → パース失敗: boats=0, trifecta空"
            f" HTML長={len(html)}文字"
        )
        return None

    return {
        "race_date": race_date,
        "race_stadium_number": int(jcd),
        "race_number": int(rno),
        "boats": boats,
        "payouts": payouts,
    }


def fetch_result_rows(target_date, venue_ids=None):
    """
    結果取得。

    venue_ids を渡した場合:
      指定場だけ取得する。

    venue_ids 未指定の場合:
      環境変数 BACKFILL_VENUES / TARGET_VENUES を見て、
      それもなければ TARGET_VENUES のデフォルト場を取得する。
    """
    hd = str(target_date).replace("-", "")
    race_date = f"{hd[:4]}-{hd[4:6]}-{hd[6:8]}"

    target_venues = _normalize_venues(venue_ids)

    print("RESULT SCRAPE:", hd)
    print("RESULT TARGET VENUES:", ",".join(sorted(target_venues)))

    rows = []
    source_url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?hd={hd}"

    for jcd in sorted(target_venues):
        for rno in RACE_NUMBERS:
            html, url = _fetch_race_result_html(hd, jcd, rno)

            if not html:
                continue

            row = _parse_race_result(html, race_date, jcd, rno)

            if row:
                rows.append(row)
                print(f"  ✅ {jcd} R{rno} 着順={len(row['boats'])}艇")
            else:
                print(f"  ⚠️  {jcd} R{rno} データなし")

            time.sleep(0.3)

    print(f"RESULT ROWS: {len(rows)}")
    return rows, source_url


def debug_print_row(row, idx=None):
    print("=== RESULT ROW DEBUG START ===")
    if idx is not None:
        print("ROW INDEX:", idx)
    print(json.dumps(row, ensure_ascii=False, indent=2))
    print("=== RESULT ROW DEBUG END ===")


def _safe_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(float(v))
    except Exception:
        return default


def _norm_ticket(v):
    if v is None:
        return None

    s = str(v).strip().replace(" ", "")
    return s if s else None


def _pick_payout(payouts, key):
    rows = payouts.get(key, [])

    if not rows:
        return None, 0

    row = rows[0]

    ticket = _norm_ticket(row.get("combination"))
    payout = _safe_int(row.get("payout"), 0)

    return ticket, payout


def _extract_places(boats):
    pairs = []

    for b in boats:
        place_no = b.get("racer_place_number")
        boat_no = b.get("racer_boat_number")

        if place_no in (None, "") or boat_no in (None, ""):
            continue

        try:
            pairs.append((int(place_no), int(boat_no)))
        except Exception:
            continue

    pairs.sort(key=lambda x: x[0])

    ordered = [boat_no for _, boat_no in pairs]
    lanes = ordered + [None] * (6 - len(ordered))

    return lanes[:6]


def parse_result_row(row):
    race_date = row.get("race_date")
    stadium_no = row.get("race_stadium_number")
    race_no = row.get("race_number")

    if not race_date or stadium_no is None or race_no is None:
        return None

    hd = str(race_date).replace("-", "")
    venue_id = str(stadium_no).zfill(2)
    race_no = int(race_no)

    race_id = f"{hd}_{venue_id}_{race_no:02d}"

    payouts = row.get("payouts", {}) or {}

    trifecta_ticket, trifecta_payout_yen = _pick_payout(
        payouts,
        "trifecta",
    )

    exacta_ticket, exacta_payout_yen = _pick_payout(
        payouts,
        "exacta",
    )

    boats = row.get("boats", []) or []

    (
        first_lane,
        second_lane,
        third_lane,
        fourth_lane,
        fifth_lane,
        sixth_lane,
    ) = _extract_places(boats)

    return {
        "race_id": race_id,
        "first_lane": first_lane,
        "second_lane": second_lane,
        "third_lane": third_lane,
        "fourth_lane": fourth_lane,
        "fifth_lane": fifth_lane,
        "sixth_lane": sixth_lane,
        "trifecta_ticket": trifecta_ticket,
        "trifecta_payout_yen": trifecta_payout_yen,
        "exacta_ticket": exacta_ticket,
        "exacta_payout_yen": exacta_payout_yen,
        "result_status": "official",
        "source": "boatrace_scrape",
    }


if __name__ == "__main__":
    rows, url = fetch_result_rows(
        "2025-04-01",
        venue_ids=[
            "02", "03", "04", "05",
            "07", "08", "09", "10", "11",
            "13", "14", "15", "16", "17",
            "19", "20", "21", "22", "23",
        ],
    )

    print("取得件数:", len(rows))

    for row in rows[:3]:
        debug_print_row(row)
        parsed = parse_result_row(row)
        print("PARSED:", parsed)