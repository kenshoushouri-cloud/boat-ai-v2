# -*- coding: utf-8 -*-
"""Read-only audit of externally verified motor-generation checkpoints.

艇国DB is used only as a manually verified secondary checkpoint date.
Automated HTTP access hits BOAT RACE official only. The audit deliberately
separates "event first day" from "representative motor present": a motor
number missing from an official ranking table is evidence that the chosen
representative is not suitable for that checkpoint, not that the checkpoint
start date itself is false.

No DB writes and no page persistence.
"""
from __future__ import annotations

from datetime import date
import re
import requests
from bs4 import BeautifulSoup

# Secondary checkpoints manually verified from 艇国DB pages.
# Representative motor is optional corroborating evidence only.
CASES = [
    {"venue": "13", "hd": "20250402", "motor_no": "1", "label": "Amagasaki"},
    {"venue": "24", "hd": "20250622", "motor_no": "11", "label": "Omura"},
]


def fetch_text(session: requests.Session, url: str) -> str:
    r = session.get(url, timeout=20)
    print(f"MOTOR_FIRSTSEEN_HTTP=status:{r.status_code} host:{r.url.split('/')[2]}", flush=True)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)


def main() -> None:
    print("MOTOR_FIRSTSEEN_MODE=official_http_read_only", flush=True)
    print("MOTOR_FIRSTSEEN_POLICY=checkpoint_date_primary_motor_number_advisory", flush=True)
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    passed = 0
    advisory_misses = 0

    for case in CASES:
        venue = case["venue"]
        hd = case["hd"]
        motor_no = case["motor_no"]
        race_url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?hd={hd}&jcd={venue}"
        motor_url = f"https://www.boatrace.jp/owpc/pc/race/rankingmotor?hd={hd}&jcd={venue}"
        race_text = re.sub(r"\s+", "", fetch_text(s, race_url))
        motor_text = re.sub(r"\s+", "", fetch_text(s, motor_url))

        # Primary checkpoint: the externally verified start date must be an
        # official event first day, and an official motor-ranking table must
        # exist for that event/date.
        first_day = ("初日" in race_text) and (hd[4:6].lstrip("0") + "月" in race_text)
        has_table = "モーター抽選結果" in motor_text and "2連対率" in motor_text

        # Advisory corroboration only. rankingmotor is not guaranteed to list
        # every motor number, so absence must not invalidate the start date.
        has_motor = bool(re.search(rf"(?:^|\D){re.escape(str(int(motor_no)))}(?:\D|$)", motor_text))
        advisory_misses += int(not has_motor)
        ok = first_day and has_table
        checkpoint_date = date(int(hd[:4]), int(hd[4:6]), int(hd[6:8]))
        print(
            f"MOTOR_FIRSTSEEN_CASE=venue:{venue} label:{case['label']} checkpoint:{checkpoint_date} "
            f"motor:{motor_no} official_first_day:{int(first_day)} motor_table:{int(has_table)} "
            f"motor_present_advisory:{int(has_motor)} pass:{int(ok)}",
            flush=True,
        )
        passed += int(ok)

    print(
        f"MOTOR_FIRSTSEEN_SUMMARY=pass:{passed}/{len(CASES)} advisory_motor_misses:{advisory_misses}",
        flush=True,
    )
    if passed != len(CASES):
        print("MOTOR_FIRSTSEEN_RESULT=FAIL", flush=True)
        raise SystemExit(2)
    print("MOTOR_FIRSTSEEN_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
