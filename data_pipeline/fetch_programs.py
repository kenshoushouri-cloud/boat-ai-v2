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

    # ✅ デバッグ：テーブルの中身を確認
    all_tables = soup.find_all("table")
    print(f"TABLE COUNT: {len(all_tables)}")
    for i, t in enumerate(all_tables[:3]):
        rows = t.find_all("tr")
        print(f"  TABLE[{i}] rows={len(rows)}")
        for j, tr in enumerate(rows[:3]):
            tds = tr.find_all(["td", "th"])
            texts = [td.get_text(strip=True)[:10] for td in tds]
            print(f"    TR[{j}]: {texts}")

    return None

    # レースタイトル
    race_title = ""
    title_el = soup.find("h3", class_="is-title4-titleBold")
    if title_el:
        race_title = title_el.get_text(strip=True)

    # 締切時刻
    race_closed_at = None
    time_el = soup.find("p", class_="is-timeBar1")
    if time_el:
        time_text = time_el.get_text(strip=True)
        try:
            date_str = f"{hd[:4]}-{hd[4:6]}-{hd[6:8]}"
            race_closed_at = f"{date_str}T{time_text}:00+09:00"
        except Exception:
            pass

    # 出走表テーブル
    boats = []
    table = soup.find("table", class_="is-w748")
    if not table:
        return None

    for tr in table.find_all("tr", class_="is-fs12"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        try:
            boat_no = int(tds[0].get_text(strip=True))
            racer_info = tds[2].get_text(strip=True)
            racer_no_el = tds[2].find("a")
            racer_no = int(racer_no_el.get_text(strip=True)) if racer_no_el else None
            racer_name_el = tds[2].find("span")
            racer_name = racer_name_el.get_text(strip=True) if racer_name_el else ""

            # 級別・支部・年齢・体重
            racer_class = None
            branch_no = None
            age = None
            weight = None
            info_tds = tds[2].find_all("span")

            # モーター・ボート番号・勝率
            motor_no = None
            motor_place2 = None
            boat_no2 = None
            boat_place2 = None

            try:
                motor_no = int(tds[3].get_text(strip=True).split()[0])
            except Exception:
                pass
            try:
                motor_place2 = float(tds[3].get_text(strip=True).split()[-1])
            except Exception:
                pass
            try:
                boat_no2 = int(tds[4].get_text(strip=True).split()[0])
            except Exception:
                pass
            try:
                boat_place2 = float(tds[4].get_text(strip=True).split()[-1])
            except Exception:
                pass

            boats.append({
                "racer_boat_number": boat_no,
                "racer_number": racer_no,
                "racer_name": racer_name,
                "racer_class_number": racer_class,
                "racer_branch_number": branch_no,
                "racer_age": age,
                "racer_weight": weight,
                "racer_motor_number": motor_no,
                "racer_motor_place2_rate": motor_place2,
                "racer_boat_number2": boat_no2,
                "racer_boat_place2_rate": boat_place2,
                "racer_national_win_rate": None,
                "racer_national_place2_rate": None,
                "racer_local_win_rate": None,
                "racer_local_place2_rate": None,
                "racer_tilt": None,
                "racer_f_count": 0,
                "racer_l_count": 0,
            })
        except Exception as e:
            print(f"boat parse error: {e}")
            continue

    if not boats:
        return None

    return {
        "race_stadium_number": int(jcd),
        "race_number": int(rno),
        "race_title": race_title,
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
