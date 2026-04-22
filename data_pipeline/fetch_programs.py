# -*- coding: utf-8 -*-
import requests

BASE_URL = "https://boatraceopenapi.github.io/programs/v2"
TARGET_VENUES = {"01", "06", "12", "18", "24"}


def fetch_programs_api(target_date):
    """
    target_date: '2026-04-20'
    """
    compact = target_date.replace("-", "")
    year = compact[:4]
    url = f"{BASE_URL}/{year}/{compact}.json"

    print("PROGRAM API:", url)

    res = requests.get(url, timeout=20)
    res.raise_for_status()

    data = res.json()
    return data.get("programs", [])


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
        "source": "boatrace_openapi",
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
