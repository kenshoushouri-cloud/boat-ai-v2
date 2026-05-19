# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

sys.path.append(os.path.dirname(__file__))

from db.client import upsert


LEGACY_VENUES_DEFAULT = ["01", "06", "12", "18", "24"]
RNO = 1

# 01 桐生 / 07 蒲郡 / 12 住之江 / 15 丸亀 / 18 下関 / 20 若松 / 24 大村
NIGHT_VENUES = {"01", "07", "12", "15", "18", "20", "24"}

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.boatrace.jp/",
}


def _env_list(name, default_values):
    raw = os.getenv(name, "")
    if not raw.strip():
        return list(default_values)
    return [v.strip().zfill(2) for v in raw.split(",") if v.strip()]


def _env_bool(name, default=True):
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _env_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def daterange(start_date, end_date):
    cur = start_date
    while cur <= end_date:
        yield cur
        cur += timedelta(days=1)


def _zen_to_han(s):
    if s is None:
        return ""
    return str(s).translate(str.maketrans("０１２３４５６７８９", "0123456789"))


def _safe_int(v, default=None):
    try:
        if v is None or v == "":
            return default
        return int(float(str(v).replace(",", "")))
    except Exception:
        return default


def _safe_float(v, default=None):
    try:
        if v is None or v == "":
            return default
        return float(str(v).replace(",", ""))
    except Exception:
        return default


def _extract_numbers(text):
    text = _zen_to_han(text)
    nums = []

    for p in re.findall(r"\d+\.\d+|\d+", text):
        try:
            nums.append(float(p))
        except Exception:
            pass

    return nums


def _parse_fl_st(text):
    text = _zen_to_han(text).replace(" ", "")
    f_count = 0
    l_count = 0
    avg_st = None

    m = re.search(r"F(\d+)L(\d+)([\d.]+)", text)
    if m:
        f_count = _safe_int(m.group(1), 0) or 0
        l_count = _safe_int(m.group(2), 0) or 0
        avg_st = _safe_float(m.group(3), None)

    return f_count, l_count, avg_st


def _parse_rate_pair(td):
    nums = []

    try:
        for t in td.stripped_strings:
            nums.extend(_extract_numbers(t))
    except Exception:
        pass

    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return nums[0], None

    return None, None


def _pick_racer_name(td):
    try:
        texts = [t.strip() for t in td.stripped_strings if t.strip()]
    except Exception:
        return ""

    for t in texts:
        t2 = _zen_to_han(t)

        if t2 in {"A1", "A2", "B1", "B2"}:
            continue
        if "/" in t2:
            continue
        if re.fullmatch(r"\d+", t2):
            continue
        if len(t2) >= 2:
            return t

    return ""


def _fetch_racelist_html(hd, jcd, rno=1):
    url = (
        "https://www.boatrace.jp/owpc/pc/race/racelist"
        f"?rno={int(rno)}&jcd={str(jcd).zfill(2)}&hd={hd}"
    )

    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=20)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text, url
    except Exception as e:
        print(f"    ❌ racelist fetch error: jcd={jcd} R{rno} {e}")
        return None, url


def _fetch_result_html(hd, jcd, rno=1):
    url = (
        "https://www.boatrace.jp/owpc/pc/race/raceresult"
        f"?rno={int(rno)}&jcd={str(jcd).zfill(2)}&hd={hd}"
    )

    try:
        r = requests.get(url, headers=HTTP_HEADERS, timeout=20)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text, url
    except Exception as e:
        print(f"    ❌ result fetch error: jcd={jcd} R{rno} {e}")
        return None, url


def _parse_entry_tr(tds):
    if len(tds) < 8:
        return None

    boat_text = _zen_to_han(tds[0].get_text(strip=True))
    m_boat = re.search(r"[1-6]", boat_text)

    if not m_boat:
        return None

    lane = int(m_boat.group())

    if not (1 <= lane <= 6):
        return None

    racer_name = _pick_racer_name(tds[1])

    racer_no = None
    m_no = re.search(r"\d{4}", _zen_to_han(tds[2].get_text(" ", strip=True)))
    if m_no:
        racer_no = int(m_no.group())

    f_count, l_count, avg_st = _parse_fl_st(tds[3].get_text(" ", strip=True))

    national_win, national_p2 = _parse_rate_pair(tds[4])
    local_win, local_p2 = _parse_rate_pair(tds[5])

    motor_no = None
    motor_p2 = None
    motor_nums = _extract_numbers(tds[6].get_text(" ", strip=True))

    if len(motor_nums) >= 1:
        motor_no = int(motor_nums[0])
    if len(motor_nums) >= 2:
        motor_p2 = motor_nums[1]

    boat_no2 = None
    boat_p2 = None
    boat_nums = _extract_numbers(tds[7].get_text(" ", strip=True))

    if len(boat_nums) >= 1:
        boat_no2 = int(boat_nums[0])
    if len(boat_nums) >= 2:
        boat_p2 = boat_nums[1]

    return {
        "racer_boat_number": lane,
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
    }


def _parse_racelist(html, hd, jcd, rno=1):
    soup = BeautifulSoup(html, "html.parser")

    if soup.find(string=lambda t: t and "データがありません" in t):
        return None

    boats_by_lane = {}

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            entry = _parse_entry_tr(tds)

            if not entry:
                continue

            lane = entry["racer_boat_number"]
            boats_by_lane[lane] = entry

        if len(boats_by_lane) >= 6:
            break

    boats = [boats_by_lane[k] for k in sorted(boats_by_lane.keys())]

    if len(boats) < 6:
        print(f"    ⚠️ racelist parse不足: venue={jcd} R{rno} boats={len(boats)}")
        return None

    race_closed_at = None

    try:
        text = soup.get_text("\n")
        times = re.findall(r"\b\d{1,2}:\d{2}\b", text)

        if times:
            time_str = times[0]
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


def build_race_id(target_date, venue_id, race_no):
    compact = target_date.replace("-", "")
    return f"{compact}_{str(venue_id).zfill(2)}_{int(race_no):02d}"


def _detect_session_type(venue_id):
    venue_id = str(venue_id).zfill(2)
    return "night" if venue_id in NIGHT_VENUES else "day"


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
        "session_type": _detect_session_type(venue_id),
        "source": "repair_legacy_r1",
        "status": "scheduled",
    }


def parse_entry_rows(row, target_date):
    venue_id = str(row.get("race_stadium_number", "")).zfill(2)
    race_no = int(row.get("race_number", 0))
    race_id = build_race_id(target_date, venue_id, race_no)

    entries = []

    for boat in row.get("boats", []):
        lane = boat.get("racer_boat_number")

        entries.append({
            "race_id": race_id,
            "lane": lane,
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
            "boat_no": boat.get("racer_boat_number2") or lane,
            "boat_place2_rate": boat.get("racer_boat_place2_rate"),
            "tilt": boat.get("racer_tilt"),
            "assumed_course": lane,
            "avg_st": boat.get("racer_avg_st"),
        })

    return entries


def _parse_race_result_fixed(html, race_date, jcd, rno):
    soup = BeautifulSoup(html, "html.parser")

    if soup.find(string=lambda t: t and "データがありません" in t):
        return None

    full_text = soup.get_text(separator="\n")
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    boats = []
    seen_places = set()

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")

            if len(tds) < 2:
                continue

            try:
                place_no = int(_zen_to_han(tds[0].get_text(strip=True)))
                boat_no = int(_zen_to_han(tds[1].get_text(strip=True)))

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

    payouts = {"trifecta": [], "exacta": []}

    i = 0

    while i < len(lines):
        line = lines[i]

        if line in ("3連単", "2連単"):
            kind = "trifecta" if line == "3連単" else "exacta"

            combo_parts = []
            j = i + 1

            while j < len(lines) and len(combo_parts) < 10:
                val = _zen_to_han(lines[j])

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
                    digits = "".join(c for c in _zen_to_han(lines[j]) if c.isdigit())
                    candidate = int(digits) if digits else 0

                    if candidate >= 100:
                        payout_yen = candidate
                        j += 1
                        break

                    j += 1

                payouts[kind].append({
                    "combination": combo,
                    "payout": payout_yen,
                })

            i = j
            continue

        i += 1

    if not boats and not payouts["trifecta"]:
        return None

    return {
        "race_date": race_date,
        "race_stadium_number": int(jcd),
        "race_number": int(rno),
        "boats": boats,
        "payouts": payouts,
    }


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
    payout = _safe_int(row.get("payout"), 0) or 0

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
        "source": "repair_legacy_r1",
    }


def repair_one_race(target_date, venue_id, sleep_sec=0.3, do_results=True):
    hd = target_date.replace("-", "")
    venue_id = str(venue_id).zfill(2)
    race_id = build_race_id(target_date, venue_id, RNO)

    print(f"\n=== repair R1 start: {race_id} ===")

    html, _ = _fetch_racelist_html(hd, venue_id, RNO)

    if not html:
        print(f"  ❌ racelist fetch failed: {race_id}")
        return False

    row = _parse_racelist(html, hd, venue_id, RNO)

    if not row:
        print(f"  ⬜ racelist no data / parse failed: {race_id}")
        return False

    race_data = parse_race_row(row, target_date)

    upsert(
        "v2_races",
        race_data,
        on_conflict=["race_id"],
    )

    print(f"  ✅ v2_races upsert: {race_id}")

    entries = parse_entry_rows(row, target_date)

    for entry in entries:
        upsert(
            "v2_race_entries",
            entry,
            on_conflict=["race_id", "lane"],
        )

    print(f"  ✅ v2_race_entries upsert: {race_id} entries={len(entries)}")

    if do_results:
        time.sleep(sleep_sec)

        result_html, _ = _fetch_result_html(hd, venue_id, RNO)

        if result_html:
            result_row = _parse_race_result_fixed(result_html, target_date, venue_id, RNO)

            if result_row:
                parsed = parse_result_row(result_row)

                if parsed:
                    upsert(
                        "v2_results",
                        parsed,
                        on_conflict=["race_id"],
                    )

                    print(
                        f"  ✅ v2_results upsert: {race_id}"
                        f" 3連単={parsed.get('trifecta_ticket')}"
                        f" {parsed.get('trifecta_payout_yen')}円"
                    )
                else:
                    print(f"  ⚠️ result parse_result_row failed: {race_id}")
            else:
                print(f"  ⚠️ result no data / parse failed: {race_id}")

    return True


def _repair_task(args):
    target_date, venue_id, sleep_sec, do_results = args
    race_id = build_race_id(target_date, venue_id, RNO)

    try:
        success = repair_one_race(
            target_date=target_date,
            venue_id=venue_id,
            sleep_sec=sleep_sec,
            do_results=do_results,
        )

        return {
            "race_id": race_id,
            "target_date": target_date,
            "venue_id": venue_id,
            "success": success,
            "error": None,
        }

    except Exception as e:
        return {
            "race_id": race_id,
            "target_date": target_date,
            "venue_id": venue_id,
            "success": False,
            "error": str(e),
        }


def run_odds_for_touched_dates(touched_dates, venues, max_workers=1):
    try:
        from app.jobs.odds_seed_job import run_odds_seed_job
    except Exception as e:
        print(f"⚠️ odds_seed_job import不可 → oddsスキップ: {e}")
        return

    venues_csv = ",".join(sorted({str(v).zfill(2) for v in venues}))

    os.environ["TARGET_VENUES"] = venues_csv
    os.environ["BACKFILL_VENUES"] = venues_csv

    dates = sorted(touched_dates)

    print("\n=== 1R odds補修開始 ===")
    print("対象日数:", len(dates))
    print("対象場:", venues_csv)
    print("odds並列数:", max_workers)

    def _odds_task(d):
        try:
            print(f"\n--- odds_seed_job: {d} ---")
            run_odds_seed_job(d)
            return d, True, None
        except Exception as e:
            return d, False, str(e)

    if max_workers <= 1:
        for d in dates:
            d, ok, err = _odds_task(d)

            if ok:
                print(f"  ✅ odds_seed_job ok: {d}")
            else:
                print(f"  ❌ odds_seed_job failed: {d} {err}")

        return

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_odds_task, d) for d in dates]

        for future in as_completed(futures):
            d, ok, err = future.result()

            if ok:
                print(f"  ✅ odds_seed_job ok: {d}")
            else:
                print(f"  ❌ odds_seed_job failed: {d} {err}")


def main():
    start_date_str = os.getenv("REPAIR_START_DATE", "2025-03-13")
    end_date_str = os.getenv("REPAIR_END_DATE", "2025-03-31")
    venues = _env_list("REPAIR_VENUES", LEGACY_VENUES_DEFAULT)

    sleep_sec = _env_float("REPAIR_SLEEP_SEC", 0.3)
    do_results = _env_bool("REPAIR_DO_RESULTS", True)
    do_odds = _env_bool("REPAIR_DO_ODDS", True)

    repair_workers = _env_int("REPAIR_WORKERS", 3)
    odds_workers = _env_int("REPAIR_ODDS_WORKERS", 1)

    if repair_workers < 1:
        repair_workers = 1
    if repair_workers > 5:
        print("⚠️ REPAIR_WORKERS は最大5に制限します")
        repair_workers = 5

    if odds_workers < 1:
        odds_workers = 1
    if odds_workers > 3:
        print("⚠️ REPAIR_ODDS_WORKERS は最大3に制限します")
        odds_workers = 3

    print("=== 旧5場 1R 専用補修開始 ===")
    print("期間:", start_date_str, "→", end_date_str)
    print("対象場:", ",".join(venues))
    print("do_results:", do_results)
    print("do_odds:", do_odds)
    print("repair並列数:", repair_workers)
    print("odds並列数:", odds_workers)
    print("sleep_sec:", sleep_sec)

    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

    tasks = []

    for d in daterange(start_date, end_date):
        target_date = d.strftime("%Y-%m-%d")

        for venue_id in venues:
            tasks.append((target_date, venue_id, sleep_sec, do_results))

    ok = []
    ng = []
    touched_dates = set()

    print("補修対象レース数:", len(tasks))

    if repair_workers == 1:
        for task in tasks:
            result = _repair_task(task)

            if result["success"]:
                ok.append(result["race_id"])
                touched_dates.add(result["target_date"])
                print("✅ repair ok:", result["race_id"])
            else:
                ng.append(result["race_id"])
                print("⬜ repair ng:", result["race_id"], result["error"] or "")

            time.sleep(sleep_sec)

    else:
        with ThreadPoolExecutor(max_workers=repair_workers) as executor:
            futures = [executor.submit(_repair_task, task) for task in tasks]

            for future in as_completed(futures):
                result = future.result()

                if result["success"]:
                    ok.append(result["race_id"])
                    touched_dates.add(result["target_date"])
                    print("✅ repair ok:", result["race_id"])
                else:
                    ng.append(result["race_id"])
                    print("⬜ repair ng:", result["race_id"], result["error"] or "")

    if do_odds and touched_dates:
        run_odds_for_touched_dates(
            touched_dates=touched_dates,
            venues=venues,
            max_workers=odds_workers,
        )

    print("\n=== 旧5場 1R 専用補修終了 ===")
    print("成功:", len(ok))
    print("失敗/データなし:", len(ng))

    if ng:
        print("\n失敗/データなし race_id sample:")
        for r in ng[:50]:
            print(" ", r)


if __name__ == "__main__":
    main()