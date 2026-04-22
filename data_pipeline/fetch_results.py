# -*- coding: utf-8 -*-
import json
import time
import requests
from bs4 import BeautifulSoup

TARGET_VENUES = ["01", "06", "12", "18", "24"]
RACE_NUMBERS = range(1, 13)


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
        print(f"fetch error: {jcd} R{rno} {e}")
        return None, url


def _parse_race_result(html, race_date, jcd, rno):
    soup = BeautifulSoup(html, "html.parser")

    no_data = soup.find(string=lambda t: t and "データがありません" in t)
    if no_data:
        return None

    full_text = soup.get_text(separator="\n")
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    # ✅ 払戻デバッグ：3連単・2連単周辺を出力
    for i, line in enumerate(lines):
        if "3連単" in line or "2連単" in line:
            start = max(0, i - 1)
            end = min(len(lines), i + 6)
            print(f"PAYOUT CONTEXT [{jcd} R{rno}]:")
            for l in lines[start:end]:
                print(f"  '{l}'")
            break

    return None  # デバッグ中は一時的にNoneを返す


def fetch_result_rows(target_date):
    hd = str(target_date).replace("-", "")
    race_date = f"{hd[:4]}-{hd[4:6]}-{hd[6:8]}"

    print("RESULT SCRAPE:", hd)

    rows = []
    source_url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?hd={hd}"

    for jcd in TARGET_VENUES:
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
    trifecta_ticket, trifecta_payout_yen = _pick_payout(payouts, "trifecta")
    exacta_ticket, exacta_payout_yen = _pick_payout(payouts, "exacta")

    boats = row.get("boats", []) or []
    first_lane, second_lane, third_lane, fourth_lane, fifth_lane, sixth_lane = _extract_places(boats)

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
    rows, url = fetch_result_rows("2026-04-20")
    print("取得件数:", len(rows))
    for row in rows[:3]:
        debug_print_row(row)
        parsed = parse_result_row(row)
        print("PARSED:", parsed)
