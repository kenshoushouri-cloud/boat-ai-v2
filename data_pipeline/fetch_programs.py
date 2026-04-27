# -*- coding: utf-8 -*-
import re
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


def _parse_fl_st(text):
    """
    'F0L00.19' -> (f_count=0, l_count=0, avg_st=0.19)
    'F1L00.14' -> (f_count=1, l_count=0, avg_st=0.14)
    """
    f_count = 0
    l_count = 0
    avg_st = None
    try:
        m = re.search(r'F(\d+)L(\d+)([\d.]+)', text.replace(" ", ""))
        if m:
            f_count = int(m.group(1))
            l_count = int(m.group(2))
            avg_st = float(m.group(3))
    except Exception:
        pass
    return f_count, l_count, avg_st


def _parse_rate_pair(td):
    """
    tdから (勝率/No, 2連率) のペアを取得する
    例: '4.4326.3639.09' -> [4.43, 26.36, 39.09] の先頭2つ
    """
    try:
        texts = [t.strip() for t in td.stripped_strings]
        if not texts:
            return None, None
        # 数値を全部抽出
        nums = []
        for t in texts:
            # カンマ区切りや改行で複数入っている場合も対応
            parts = re.findall(r'[\d]+\.[\d]+|[\d]+', t)
            for p in parts:
                try:
                    nums.append(float(p))
                except Exception:
                    pass
        if len(nums) >= 2:
            return nums[0], nums[1]
        elif len(nums) == 1:
            return nums[0], None
    except Exception:
        pass
    return None, None


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
            boat_no = int(tds[0].get_text(strip=True).translate(
                str.maketrans("１２３４５６", "123456")
            ))
            if boat_no not in range(1, 7):
                i += 1
                continue

            # tds[1]: 選手名（級・支部・年齢・体重も含まれる場合あり）
            racer_td = tds[1]
            texts = [t.strip() for t in racer_td.stripped_strings]
            racer_name = ""
            for t in texts:
                if len(t) >= 2 and not t.isdigit() and "/" not in t:
                    racer_name = t
                    break

            # tds[2]: 登録番号
            racer_no = None
            try:
                reg_text = tds[2].get_text(strip=True)
                m = re.search(r'\d{4}', reg_text)
                if m:
                    racer_no = int(m.group())
            except Exception:
                pass

            # tds[3]: F回数・L回数・平均ST (例: F0L00.19)
            f_count = 0
            l_count = 0
            avg_st = None
            try:
                fl_text = tds[3].get_text(strip=True)
                f_count, l_count, avg_st = _parse_fl_st(fl_text)
            except Exception:
                pass

            # tds[4]: 全国勝率・2連率
            national_win, national_p2 = _parse_rate_pair(tds[4])

            # tds[5]: 当地勝率・2連率
            local_win, local_p2 = _parse_rate_pair(tds[5])

            # tds[6]: モーターNo・2連率
            motor_no = None
            motor_p2 = None
            try:
                mot_nums = []
                for t in tds[6].stripped_strings:
                    parts = re.findall(r'[\d]+\.[\d]+|[\d]+', t.strip())
                    for p in parts:
                        try:
                            mot_nums.append(float(p))
                        except Exception:
                            pass
                if len(mot_nums) >= 1:
                    motor_no = int(mot_nums[0])
                if len(mot_nums) >= 2:
                    motor_p2 = mot_nums[1]
            except Exception:
                pass

            # tds[7]: ボートNo・2連率
            boat_no2 = None
            boat_p2 = None
            try:
                boa_nums = []
                for t in tds[7].stripped_strings:
                    parts = re.findall(r'[\d]+\.[\d]+|[\d]+', t.strip())
                    for p in parts:
                        try:
                            boa_nums.append(float(p))
                        except Exception:
                            pass
                if len(boa_nums) >= 1:
                    boat_no2 = int(boa_nums[0])
                if len(boa_nums) >= 2:
                    boat_p2 = boa_nums[1]
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
                "racer_f_count": f_count,
                "racer_l_count": l_count,
                "racer_avg_st": avg_st,
            })

            print(
                f"    PARSE: {boat_no} {racer_name} no={racer_no}"
                f" nat={national_win}/{national_p2}"
                f" loc={local_win}/{local_p2}"
                f" motor={motor_no}/{motor_p2}"
                f" boat={boat_no2}/{boat_p2}"
                f" F{f_count}L{l_count} ST={avg_st}"
            )

        except Exception as e:
            print(f"    PARSE ERROR boat_block i={i}: {e}")

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
            "avg_st": boat.get("racer_avg_st"),
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
            print(" ", b["racer_boat_number"], b["racer_name"],
                  "nat=", b["racer_national_win_rate"],
                  "motor=", b["racer_motor_number"], b["racer_motor_place2_rate"])