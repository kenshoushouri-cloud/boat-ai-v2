# -*- coding: utf-8 -*-
"""
probe_k_specific_race_raw_pg.py

公式Kファイルから指定日・指定場・指定Rの詳細ブロックだけを
原文表示する低ログ診断用。

DB更新なし。

環境変数:
  TARGET_DATE=2026-06-06
  TARGET_VENUE=03
  TARGET_RNO=8
"""

from __future__ import annotations

import os
import re

import audit_k_day_all_pg as ka

VERSION = "2026-08-17 specific-race-raw-v1"

TARGET_DATE = os.getenv("TARGET_DATE", "2026-06-06")
TARGET_VENUE = os.getenv("TARGET_VENUE", "03").zfill(2)
TARGET_RNO = int(os.getenv("TARGET_RNO", "8"))


def main():
    print(
        f"✅ probe_k_specific_race_raw_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(
        f"TARGET_DATE={TARGET_DATE} "
        f"TARGET_VENUE={TARGET_VENUE} "
        f"TARGET_RNO={TARGET_RNO}",
        flush=True,
    )
    print("DB書き込みなし。", flush=True)

    text = ka.get_k_text(TARGET_DATE)
    lines = text.splitlines()
    sections = ka.split_venue_sections(lines)

    section = next(
        (s for s in sections if str(s.get("venue_code")) == TARGET_VENUE),
        None,
    )

    if not section:
        raise RuntimeError(f"venue section not found: {TARGET_VENUE}")

    slines = section["lines"]

    start = None
    for i, line in enumerate(slines):
        h = ka.parse_header(line)
        if h and int(h["race_no"]) == TARGET_RNO:
            start = i
            break

    if start is None:
        raise RuntimeError(
            f"detail race header not found: venue={TARGET_VENUE} rno={TARGET_RNO}"
        )

    end = len(slines)
    for i in range(start + 1, len(slines)):
        h = ka.parse_header(slines[i])
        if h:
            end = i
            break

    block = slines[start:end]

    print(
        f"venue={section.get('venue_code')}:{section.get('venue_name')} "
        f"block_lines={len(block)}",
        flush=True,
    )

    print("\n=== RAW BLOCK ===", flush=True)
    for offset, raw in enumerate(block, 1):
        print(f"{offset:03d}: {raw!r}", flush=True)

    print("\n=== PARSER RESULT PER LINE ===", flush=True)
    parsed_count = 0

    for offset, raw in enumerate(block, 1):
        parsed = ka.parse_finish_line(raw)

        if parsed:
            parsed_count += 1
            print(
                f"{offset:03d}: PARSED "
                f"lane={parsed.get('lane')} "
                f"racer={parsed.get('racer_number')} "
                f"finish={parsed.get('finish_position')} "
                f"status={parsed.get('finish_status')} "
                f"exh={parsed.get('exhibition_time')} "
                f"course={parsed.get('start_course')} "
                f"ST={parsed.get('start_timing')}",
                flush=True,
            )
        else:
            s = ka.clean(raw)

            # 艇番+登録番号が見える行は、候補正規表現に乗らなくても表示
            if re.search(r"\b[1-6]\s+\d{4}\b", s):
                print(
                    f"{offset:03d}: UNPARSED_CANDIDATE {raw!r}",
                    flush=True,
                )
                print(
                    "HEX="
                    + raw.encode(
                        "cp932",
                        errors="replace",
                    ).hex(),
                    flush=True,
                )

    print(f"\nparsed_finish_rows={parsed_count}", flush=True)
    print("RESULT=SUCCESS", flush=True)


if __name__ == "__main__":
    main()