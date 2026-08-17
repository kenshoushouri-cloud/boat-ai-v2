# -*- coding: utf-8 -*-
"""
probe_k_parser_failure_pg.py

audit_k_day_all_pg.py の実parserをそのまま使って、
指定日の parser failure / 6艇未満レースだけを特定する診断用。

DB更新なし。

環境変数:
  TARGET_DATE=2026-08-01
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import audit_k_day_all_pg as ka

VERSION = "2026-08-17 parser-failure-probe-v2"
TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-01")


def main() -> None:
    print(
        f"✅ probe_k_parser_failure_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print("DB書き込みなし。", flush=True)

    text = ka.get_k_text(TARGET_DATE)
    sections = ka.split_venue_sections(text.splitlines())

    races: List[Dict[str, Any]] = []
    for section in sections:
        races.extend(ka.parse_section(section))

    incomplete = [
        race
        for race in races
        if len(race.get("entries") or []) != 6
    ]

    failures = [
        (race, raw_line)
        for race in races
        for raw_line in race.get("parse_failed_candidate_lines") or []
    ]

    print("\n=== SUMMARY ===", flush=True)
    print(f"venue_sections={len(sections)}", flush=True)
    print(f"races={len(races)}", flush=True)
    print(
        f"entry_rows={sum(len(r.get('entries') or []) for r in races)}",
        flush=True,
    )
    print(f"incomplete_races={len(incomplete)}", flush=True)
    print(f"parser_failures={len(failures)}", flush=True)

    if incomplete:
        print("\n=== INCOMPLETE RACES ===", flush=True)

        for race in incomplete[:20]:
            entries = race.get("entries") or []

            parsed_lanes = sorted(
                int(e["lane"])
                for e in entries
                if e.get("lane") is not None
            )

            missing_lanes = [
                lane
                for lane in range(1, 7)
                if lane not in parsed_lanes
            ]

            print("-" * 88, flush=True)
            print(
                f"race_id={race.get('race_id')} "
                f"venue={race.get('venue_code')}:{race.get('venue_name')} "
                f"race_no={race.get('race_no')} "
                f"entries={len(entries)} "
                f"parsed_lanes={parsed_lanes} "
                f"missing_lanes={missing_lanes}",
                flush=True,
            )
            print(
                f"candidate_like={race.get('candidate_like')} "
                f"trifecta={race.get('trifecta_ticket')} "
                f"payout={race.get('trifecta_payout')} "
                f"winning_method={race.get('winning_method')}",
                flush=True,
            )

            for e in sorted(entries, key=lambda x: int(x["lane"])):
                print(
                    f"PARSED lane={e.get('lane')} "
                    f"racer={e.get('racer_number')} "
                    f"finish={e.get('finish_position')} "
                    f"status={e.get('finish_status')} "
                    f"motor={e.get('motor_no')} "
                    f"boat={e.get('boat_no')} "
                    f"exh={e.get('exhibition_time')} "
                    f"course={e.get('start_course')} "
                    f"ST={e.get('start_timing')}",
                    flush=True,
                )

            failed_lines = race.get("parse_failed_candidate_lines") or []

            if failed_lines:
                print("FAILED RAW:", flush=True)
                for raw_line in failed_lines[:10]:
                    print(repr(raw_line), flush=True)
                    print(
                        "HEX="
                        + raw_line.encode(
                            "cp932",
                            errors="replace",
                        ).hex(),
                        flush=True,
                    )

    if failures:
        print("\n=== ALL PARSER FAILURE ROWS ===", flush=True)

        for race, raw_line in failures[:30]:
            print(
                f"{race.get('race_id')} "
                f"{race.get('venue_code')}:{race.get('venue_name')} "
                f"{race.get('race_no')}R "
                f"RAW={raw_line!r}",
                flush=True,
            )
            print(
                "HEX="
                + raw_line.encode(
                    "cp932",
                    errors="replace",
                ).hex(),
                flush=True,
            )

    result = (
        "FOUND"
        if incomplete or failures
        else "NO_FAILURE"
    )

    print(f"\nRESULT={result}", flush=True)


if __name__ == "__main__":
    main()