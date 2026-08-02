# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Dict, List

from repair_month_all_pg import _fetch, _looks_no_race, _official_url, parse_odds3t

PROBE_DATES = [x.strip() for x in os.getenv(
    "HISTORICAL_ODDS_PROBE_DATES",
    "2025-07-01,2025-10-01,2026-01-01,2026-04-01,2026-05-01"
).split(",") if x.strip()]

PROBE_VENUES = [x.strip().zfill(2) for x in os.getenv(
    "HISTORICAL_ODDS_PROBE_VENUES", "01,12,24"
).split(",") if x.strip()]

PROBE_RACES = [int(x.strip()) for x in os.getenv(
    "HISTORICAL_ODDS_PROBE_RACES", "1,6,12"
).split(",") if x.strip()]

SLEEP_SEC = float(os.getenv("HISTORICAL_ODDS_PROBE_SLEEP_SEC", "0.5"))


def _status(count: int) -> str:
    if count == 120:
        return "COMPLETE_120"
    if count == 60:
        return "COMPLETE_60"
    if count == 24:
        return "COMPLETE_24"
    if count > 0:
        return "PARTIAL"
    return "NO_ODDS"


def main() -> None:
    print("✅ probe_historical_odds_availability_pg.py VERSION 2026-08-03 sample-probe-v1", flush=True)
    print(f"DATES={','.join(PROBE_DATES)} VENUES={','.join(PROBE_VENUES)} RACES={','.join(map(str, PROBE_RACES))}", flush=True)
    print("読み取り専用です。DB保存・LINE通知・本番変更はありません。", flush=True)

    total = complete = partial = no_race = no_odds = 0
    by_date: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for date_str in PROBE_DATES:
        print(f"\n=== {date_str} ===", flush=True)
        for venue_id in PROBE_VENUES:
            for race_no in PROBE_RACES:
                total += 1
                race_id = f"{date_str.replace('-', '')}_{venue_id}_{race_no:02d}"
                html = _fetch(_official_url("odds3t", date_str, venue_id, race_no))

                if _looks_no_race(html):
                    no_race += 1
                    by_date[date_str]["NO_RACE"] += 1
                    print(f"{race_id} status=NO_RACE rows=0", flush=True)
                    if SLEEP_SEC > 0:
                        time.sleep(SLEEP_SEC)
                    continue

                rows: List[dict] = parse_odds3t(html or "", race_id)
                count = len(rows)
                status = _status(count)
                by_date[date_str][status] += 1

                if status.startswith("COMPLETE"):
                    complete += 1
                elif status == "PARTIAL":
                    partial += 1
                else:
                    no_odds += 1

                print(f"{race_id} status={status} rows={count}", flush=True)
                if SLEEP_SEC > 0:
                    time.sleep(SLEEP_SEC)

    print("\n=== date summary ===", flush=True)
    for date_str in PROBE_DATES:
        c = by_date[date_str]
        print(
            f"{date_str}: complete120={c['COMPLETE_120']} complete60={c['COMPLETE_60']} "
            f"complete24={c['COMPLETE_24']} partial={c['PARTIAL']} "
            f"no_odds={c['NO_ODDS']} no_race={c['NO_RACE']}",
            flush=True,
        )

    print("\n=== overall summary ===", flush=True)
    print(f"total_samples={total}", flush=True)
    print(f"complete_samples={complete}", flush=True)
    print(f"partial_samples={partial}", flush=True)
    print(f"no_odds_samples={no_odds}", flush=True)
    print(f"no_race_samples={no_race}", flush=True)

    if complete > 0:
        print("HISTORICAL_ODDS_AVAILABLE=YES", flush=True)
    else:
        print("HISTORICAL_ODDS_AVAILABLE=NOT_CONFIRMED", flush=True)

    print("=== probe finished ===", flush=True)


if __name__ == "__main__":
    main()