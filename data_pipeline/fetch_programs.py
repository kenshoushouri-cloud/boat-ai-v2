# -*- coding: utf-8 -*-
import requests
import time
from bs4 import BeautifulSoup

TARGET_VENUES = {"01", "06", "12", "18", "24"}
RACE_NUMBERS = range(1, 13)


def _fetch_racelist_html(hd, jcd, rno):
    url = (
        f"https://www.boatrace.jp/owpc/pc/race/racelist"
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
        print(f"fetch_racelist error: jcd={jcd} rno={rno} {e}")
        return None, url


def _parse_racelist(html, hd, jcd, rno):
    soup = BeautifulSoup(html, "html.parser")

    all_tables = soup.find_all("table")
    if len(all_tables) < 2:
        return None

    # TABLE[1] が出走表（ヘッダー3行 + 艇ごと4行）
    table = all_tables[1]
    all_trs = table.find_all("tr")
    data_trs = all_trs[3:]

    boats = []
    i = 0
    while i < len(data_trs):
        block = data_trs[i:i + 4]
        if not block:
            break

        tr0 = block[0]
        tds = tr0.find_all(["td", "th"])

        try:
            boat_no = int(tds[0].get_text(strip=True))
            if boat_no not in range(1, 7):
                i += 1
                continue

            # 登録番号・氏名
            racer_td = tds[1]
            texts = [t.strip() for t in racer_td.stripped_strings]
            racer_no = None
            racer_name = ""
            for t in texts:
                if t.isdigit() and len(t) == 4:
                    racer_no = int(t)
                elif len(t) <= 10 and not t.isdigit() and "/" not in t:
                    if racer_name == "":
                        racer_name = t

            # 全国勝率・2連率
            national_win = None
            national_p2 = None
            try:
                nat_texts = [t.strip() for t in tds[3].stripped_strings]
                if len(nat_texts) >= 1:
                    national_win = float(nat_texts[0])
                if len(nat_texts) >= 2:
                    national_p2 = float(nat_texts[1])
            except Exception:
                pass

            # 当地勝率・2連率
            local_win = None
            local_p2 = None
            try:
                loc_texts = [t.strip() for t in tds[4].stripped_strings]
                if len(loc_texts) >= 1:
                    local_win = float(loc_texts[0])
                if len(loc_texts) >= 2:
                    local_p2 = float(loc_texts[1])
            except Exception:
                pass

            # モーターNo・2連率
            motor_no = None
            motor_p2 = None
            try:
                mot_texts = [t.strip() for t in tds[5].stripped_strings]
                if len(mot_texts) >= 1:
                    motor_no = int(mot_texts[0])
                if len(mot_texts) >= 2:
                    motor_p2 = float(mot_texts[1])
            except Exception:
                pass

            # ボートNo・2連率
            boat_no2 = None
            boat_p2 = None
            try:
                boa_texts = [t.strip() for t in tds[6].stripped_strings]
                if len(boa_texts) >= 1:
                    boat_no2 = int(boa_texts[0])
                if len(boa_texts) >= 2:
                    boat_p2 = float(boa_texts[1])
            except Exception:
                pass

            boats.append({
                "racer_boat_number": boat_no,
                "racer_number": racer_no,
                "racer_name": racer_name,
                "racer_class_number": None,
                "racer_branch_number": None,
                "racer_age": None,
                "racer_weight": None,
                "racer_motor_number": motor_no,
                "racer_motor_place2_rate": motor_p2,
                "racer_boat_number2": boat_no2,
                "racer_boat_place2_rate": boat_p2,
                "racer_national_win_rate": national_win,
                "racer_national_place2_rate": national_p2,
                "racer_local_win_rate": local_win,
                "racer_local_place2_rate": local_p2,
                "racer_tilt": None,
                "racer_f_count": 0,
                "racer_l_count": 0,
            })

        except Exception:
            pass

        i += 4

    if not boats:
        return None

    # 締切時刻（TABLE[0] の2行目から取得）
    race_closed_at = None
    try:
        t0_trs = all_tables[0].find_all("tr")
        times = [td.get_text(strip=True) for td in t0_trs[1].find_all("td")]
        time_str = times[rno - 1] if rno <= len(times) else None
        if time_str:
            date_str = f"{hd[:4]}-{hd[4:6]}-{hd[6:8]}"
            race_closed_at = f"{date_str}T{time_str}:00+09:00"
    except Exception:
        pass

    return {
        "race_stadium_number": int(jcd),
        "race_number": int(rno),
        "race_title": "",
        "race_closed_at": race_closed_at,
        "boats": boats,
    }


def fetch_programs_api(target_date):
    """
    target_date: '2026-04-20'
    boatrace.jpからスクレイピングしてOpenAPI互換の形式で返す
    """
    hd = target_date.replace("-", "")
    print("PROGRAM SCRAPE:", hd)

    rows = []
    for jcd in sorted(TARGET_VENUES):
        for rno in RACE_NUMBERS:
            html, url = _fetch_racelist_html(hd, jcd, rno)
            if not html:
                continue
            row = _parse_racelist(html, hd, jcd, rno)
            if row:
                rows.append(row)
                print(f"  ✅ {jcd} R{rno} 艇数={len(row['boats'])}")
            else:
                print(f"  ⚠️  {jcd} R{rno} データなし")
            time.sleep(0.3)

    print(f"PROGRAM ROWS: {len(rows)}")
    return rows


def build_race_id(target_date, venue_id, race_no):
    compact = target_date.replace("-", "")
    return f"{compact}_{str(venue_id).zfill(2)}_{int(race_no):02d}"


def parse_race_row(row, target_date):
    venue_id = str(row.get("race_stadium_number", "")).zfill(2)
    race_no = int(row.get("race_number", 0))
    return {
        "race_id": build_race_id(target_date, venue_id, race_no),
        "race_date": target_date,
        "venue_id": venue_id,
        "race_no": race_no,
        "race_title": row.get("race_title") or "",
        "race_closed_at": row.get("race_closed_at"),
        "session_type": "day",
        "source": "boatrace_scrape",
        "status": "scheduled",
    }


def parse_entry_rows(row, target_date):
    venue_id = str(row.get("race_stadium_number", "")).zfill(2)
    race_no = int(row.get("race_number", 0))
    race_id = build_race_id(target_date, venue_id, race_no)

    entries = []
    for boat in row.get("boats", []):
        entry = {
            "race_id": race_id,
            "lane": boat.get("racer_boat_number"),
            "entry_number": boat.get("racer_number"),
            "racer_number": boat.get("racer_number"),
            "racer_name": boat.get("racer_name", ""),
            "racer_class": boat.get("racer_class_number"),
            "branch_number": boat.get("racer_branch_number"),
            "age": boat.get("racer_age"),
            "weight": boat.get("racer_weight"),
            "f_count": boat.get("racer_f_count", 0) or 0,
            "l_count": boat.get("racer_l_count", 0) or 0,
            "national_win_rate": boat.get("racer_national_win_rate"),
            "national_place2_rate": boat.get("racer_national_place2_rate"),
            "local_win_rate": boat.get("racer_local_win_rate"),
            "local_place2_rate": boat.get("racer_local_place2_rate"),
            "motor_no": boat.get("racer_motor_number"),
            "motor_place2_rate": boat.get("racer_motor_place2_rate"),
            "boat_no": boat.get("racer_boat_number2") or boat.get("racer_boat_number"),
            "boat_place2_rate": boat.get("racer_boat_place2_rate"),
            "tilt": boat.get("racer_tilt"),
            "assumed_course": boat.get("racer_boat_number"),
        }
        entries.append(entry)
    return entries


if __name__ == "__main__":
    rows = fetch_programs_api("2025-04-01")
    print("取得件数:", len(rows))
    for row in rows[:2]:
        print("RACE:", row["race_stadium_number"], row["race_number"])
        print("BOATS:", len(row["boats"]))
        for b in row["boats"]:
            print(" ", b["racer_boat_number"], b["racer_name"], b["racer_national_win_rate"])
