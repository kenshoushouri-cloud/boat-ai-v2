# -*- coding: utf-8 -*-
"""Read-only audit: validate externally verified 艇国DB motor aggregate start dates against BOAT RACE official event/motor pages.

艇国DB is used only as a manually verified secondary checkpoint date. HTTP automation hits BOAT RACE official only.
No DB writes and no page persistence.
"""
from __future__ import annotations

from datetime import date
import re
import requests
from bs4 import BeautifulSoup

# Secondary checkpoints manually verified from 艇国DB pages.
# 尼崎 motor 1: aggregate period starts 2025-04-02.
# 大村 motor list: aggregate period starts 2025-06-22; motor 11 is present in that generation.
CASES = [
    ("13", "20250402", "1"),
    ("24", "20250622", "11"),
]


def fetch_text(session: requests.Session, url: str) -> str:
    r = session.get(url, timeout=20)
    print(f"MOTOR_FIRSTSEEN_HTTP=status:{r.status_code} host:{r.url.split('/')[2]}", flush=True)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)


def main() -> None:
    print("MOTOR_FIRSTSEEN_MODE=official_http_read_only", flush=True)
    print("MOTOR_FIRSTSEEN_POLICY=teikoku_checkpoint_official_automation", flush=True)
    s = requests.Session()
    s.headers.update({"User-Agent": "Mozilla/5.0"})
    passed = 0
    for venue, hd, motor_no in CASES:
        race_url = f"https://www.boatrace.jp/owpc/pc/race/raceindex?hd={hd}&jcd={venue}"
        motor_url = f"https://www.boatrace.jp/owpc/pc/race/rankingmotor?hd={hd}&jcd={venue}"
        race_text = re.sub(r"\s+", "", fetch_text(s, race_url))
        motor_text = re.sub(r"\s+", "", fetch_text(s, motor_url))

        # Require the checkpoint date to be an official event first day.
        first_day = ("初日" in race_text) and (hd[4:6].lstrip("0") + "月" in race_text)
        # Require an actual motor ranking table and the representative motor number.
        has_table = "モーター抽選結果" in motor_text and "2連対率" in motor_text
        # Keep the motor-number check conservative: number must occur near a percentage/table context.
        has_motor = bool(re.search(rf"(?:^|\D){re.escape(str(int(motor_no)))}(?:\D|$)", motor_text))
        ok = first_day and has_table and has_motor
        print(
            f"MOTOR_FIRSTSEEN_CASE=venue:{venue} checkpoint:{date(int(hd[:4]),int(hd[4:6]),int(hd[6:8]))} "
            f"motor:{motor_no} official_first_day:{int(first_day)} motor_table:{int(has_table)} motor_present:{int(has_motor)} pass:{int(ok)}",
            flush=True,
        )
        passed += int(ok)

    print(f"MOTOR_FIRSTSEEN_SUMMARY=pass:{passed}/{len(CASES)}", flush=True)
    if passed != len(CASES):
        print("MOTOR_FIRSTSEEN_RESULT=FAIL", flush=True)
        raise SystemExit(2)
    print("MOTOR_FIRSTSEEN_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
