# -*- coding: utf-8 -*-
"""
audit_k_day_all_pg.py

BOAT RACE公式Kファイルを1日分取得し、
全開催場・全Rを解析して品質監査する。

DB更新なし。

監査項目:
- venue blocks
- races
- entries count / 6艇完全率
- accident rows
- trifecta/payout
- winning_method
- weather/wind/wave
- exhibition/start_course/ST
- duplicate race ids
- parser NG sample

環境変数:
  TARGET_DATE=2026-08-16
"""

from __future__ import annotations

import os
import re
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import lhafile  # type: ignore

VERSION = "2026-08-17 k-day-all-audit-v5-l-no-course"

TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-16")
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2/1.0; +https://boatrace.jp)",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}

VENUE_NAMES = {
    "01":"桐生","02":"戸田","03":"江戸川","04":"平和島","05":"多摩川",
    "06":"浜名湖","07":"蒲郡","08":"常滑","09":"津","10":"三国",
    "11":"びわこ","12":"住之江","13":"尼崎","14":"鳴門","15":"丸亀",
    "16":"児島","17":"宮島","18":"徳山","19":"下関","20":"若松",
    "21":"芦屋","22":"福岡","23":"唐津","24":"大村",
}

# Kファイル表記は全角空白を含むため、正規化名で照合
NAME_TO_CODE = {
    re.sub(r"\s+", "", name): code
    for code, name in VENUE_NAMES.items()
}

METHODS = ("まくり差し","逃げ","差し","まくり","抜き","恵まれ")
K_ACCIDENT_PREFIXES = ("S0","S1","S2","F","L0","L1","K0","K1","転","落","沈","妨","失格","失","欠","不")


def clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def compact_name(s: str) -> str:
    return re.sub(r"[\s　]+", "", str(s or ""))


def race_id(date_str: str, venue_code: str, race_no: int) -> str:
    return f"{date_str.replace('-', '')}_{venue_code}_{race_no:02d}"


def k_url(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (
        "https://www1.mbrace.or.jp/od2/K/"
        f"{dt.strftime('%Y%m')}/k{dt.strftime('%y%m%d')}.lzh"
    )


def get_k_text(date_str: str) -> str:
    url = k_url(date_str)
    r = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    print(
        f"K_GET status={r.status_code} bytes={len(r.content)} url={url}",
        flush=True,
    )
    r.raise_for_status()

    with tempfile.TemporaryDirectory(prefix="kaudit_") as td:
        archive = Path(td) / "k.lzh"
        archive.write_bytes(r.content)
        lha = lhafile.Lhafile(str(archive))
        names = lha.namelist()
        if not names:
            raise RuntimeError("K archive has no members")
        data = lha.read(names[0])

    return data.decode("cp932")


def detect_venue_from_header(line: str) -> Optional[Tuple[str, str]]:
    """
    例:
      大　村［成績］      8/16 ...
    """
    s = str(line or "")
    m = re.search(r"(.+?)［成績］", s)
    if not m:
        return None

    raw_name = m.group(1).strip()
    normalized = compact_name(raw_name)

    # 完全一致優先
    if normalized in NAME_TO_CODE:
        code = NAME_TO_CODE[normalized]
        return code, VENUE_NAMES[code]

    # 部分一致フォールバック
    for name_norm, code in NAME_TO_CODE.items():
        if name_norm in normalized or normalized in name_norm:
            return code, VENUE_NAMES[code]

    return None


def parse_header(line: str) -> Optional[Dict[str, Any]]:
    s = clean(line)

    m = re.match(
        r"(\d{1,2})R\s+(.+?)\s+H(\d+)m\s+(.+)$",
        s,
    )
    if not m:
        return None

    tail = m.group(4)

    wm = re.search(
        r"^(.+?)\s+風\s+(.+?)\s+(\d+(?:\.\d+)?)m\s+波\s+(\d+(?:\.\d+)?)cm",
        tail,
    )

    return {
        "race_no": int(m.group(1)),
        "race_title": clean(m.group(2)),
        "distance_m": int(m.group(3)),
        "weather": clean(wm.group(1)) if wm else None,
        "wind_direction": clean(wm.group(2)) if wm else None,
        "wind_speed_m": float(wm.group(3)) if wm else None,
        "wave_height_cm": float(wm.group(4)) if wm else None,
    }


def parse_start_timing(raw: str):
    s = clean(raw)

    start_status = None
    if s.startswith("F"):
        start_status = "F"
    elif s.startswith("L"):
        start_status = "L"

    numeric = s.lstrip("FL ").strip()

    try:
        value = float(numeric) if "." in numeric else int(numeric) / 100.0
    except Exception:
        value = None

    return start_status, value


def parse_finish_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Kファイル着欄:
      01..06 = 正常着順
      00     = レース不成立等で着順なし
      F/S*/L*/K* = 事故・返還・欠場系コード

    00 は艇データ自体（展示/進入/ST）が存在する場合があるため、
    finish_position=None / finish_status="00" として保存する。
    """
    s = clean(line)

    head = re.match(
        r"^(?P<status>"
        r"00|0[1-6]|[1-6]|"
        r"S[012]|F|L[01]|K[01]|"
        r"転|落|沈|妨|失格|失|欠|不"
        r")\s+"
        r"(?P<lane>[1-6])\s+"
        r"(?P<racer>\d{4})\s+"
        r"(?P<rest>.+)$",
        s,
    )
    if not head:
        return None

    status = head.group("status")
    rest = head.group("rest")
    finish_position = int(status) if re.fullmatch(r"0?[1-6]", status) else None

    # K0 / K1 欠場系特殊行
    if status in ("K0", "K1"):
        ktail = re.match(
            r"^(?P<name>.*?)\s+"
            r"(?P<motor>\d{1,3})\s+"
            r"(?P<boat>\d{1,3})\s+"
            r"K\s*\.\s+K\s*\.\s*\.\s*\.$",
            rest,
        )
        if ktail:
            return {
                "finish_position": None,
                "finish_status": status,
                "lane": int(head.group("lane")),
                "racer_number": int(head.group("racer")),
                "racer_name": clean(ktail.group("name")),
                "motor_no": int(ktail.group("motor")),
                "boat_no": int(ktail.group("boat")),
                "exhibition_time": None,
                "start_course": None,
                "start_timing": None,
                "start_status": None,
                "is_flying": False,
                "is_late": False,
                "race_time": None,
            }

    # L0 / L1 出遅れ系特殊行
    #
    # 形式A: 進入コースあり
    #   L0 2 5357 ... 6.76 5 L . . .
    #
    # 形式B: 進入コースなし
    #   L0 1 4885 ... 6.76 L . . .
    #
    # Kファイルに進入値が存在しない場合は推測せずNULLで保存する。
    if status in ("L0", "L1"):
        ltail = re.match(
            r"^(?P<name>.*?)\s+"
            r"(?P<motor>\d{1,3})\s+"
            r"(?P<boat>\d{1,3})\s+"
            r"(?P<exh>\d+\.\d{2})\s+"
            r"(?:(?P<course>[1-6])\s+)?"
            r"L\s*\.\s*\.\s*\.$",
            rest,
        )
        if ltail:
            course_raw = ltail.group("course")
            return {
                "finish_position": None,
                "finish_status": status,
                "lane": int(head.group("lane")),
                "racer_number": int(head.group("racer")),
                "racer_name": clean(ltail.group("name")),
                "motor_no": int(ltail.group("motor")),
                "boat_no": int(ltail.group("boat")),
                "exhibition_time": float(ltail.group("exh")),
                "start_course": int(course_raw) if course_raw else None,
                "start_timing": None,
                "start_status": "L",
                "is_flying": False,
                "is_late": True,
                "race_time": None,
            }

    tail = re.match(
        r"^(?P<name>.*?)\s+"
        r"(?P<motor>\d{1,3})\s+"
        r"(?P<boat>\d{1,3})\s+"
        r"(?P<exh>\d+\.\d{2})\s+"
        r"(?P<course>[1-6])\s+"
        r"(?P<st>[FL]?\s*(?:[-+]?\d*\.\d{2}|\d{2}))"
        r"(?:\s+(?P<time>.*))?$",
        rest,
    )
    if not tail:
        return None

    start_status, start_timing = parse_start_timing(tail.group("st"))

    race_time_raw = clean(tail.group("time"))
    race_time = None
    if race_time_raw:
        compact_time = re.sub(r"\s+", "", race_time_raw)
        if compact_time not in ("..", "..."):
            first = race_time_raw.split()[0]
            if re.search(r"\d", first):
                race_time = first

    return {
        "finish_position": finish_position,
        "finish_status": status,
        "lane": int(head.group("lane")),
        "racer_number": int(head.group("racer")),
        "racer_name": clean(tail.group("name")),
        "motor_no": int(tail.group("motor")),
        "boat_no": int(tail.group("boat")),
        "exhibition_time": float(tail.group("exh")),
        "start_course": int(tail.group("course")),
        "start_timing": start_timing,
        "start_status": start_status,
        "is_flying": start_status == "F" or status == "F",
        "is_late": start_status == "L" or status in ("L0", "L1"),
        "race_time": race_time,
    }


def parse_trifecta(lines: List[str]) -> Tuple[Optional[str], Optional[int]]:
    for line in lines:
        m = re.search(
            r"３連単\s+([1-6]-[1-6]-[1-6])\s+([\d,]+)",
            clean(line),
        )
        if m:
            return (
                m.group(1),
                int(m.group(2).replace(",", "")),
            )
    return None, None


def split_venue_sections(lines: List[str]) -> List[Dict[str, Any]]:
    starts = []

    for i, line in enumerate(lines):
        v = detect_venue_from_header(line)
        if v:
            starts.append((i, v[0], v[1]))

    sections = []

    for idx, (start, code, name) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        sections.append(
            {
                "venue_code": code,
                "venue_name": name,
                "start": start,
                "end": end,
                "lines": lines[start:end],
            }
        )

    return sections


def parse_section(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    lines = section["lines"]
    detail_starts = []

    for i, line in enumerate(lines):
        h = parse_header(line)
        if h:
            detail_starts.append((i, h))

    races = []

    for idx, (start, header) in enumerate(detail_starts):
        end = detail_starts[idx + 1][0] if idx + 1 < len(detail_starts) else len(lines)
        block = lines[start:end]

        method = None
        for line in block[:6]:
            for x in METHODS:
                if x in clean(line):
                    method = x
                    break
            if method:
                break

        entries = []
        candidate_like = 0
        parse_failed_candidate_lines = []

        for line in block:
            s = clean(line)

            # race result rowらしい先頭か
            if re.match(
                r"^(00|0[1-6]|[1-6]|S[012]|F|L[01]|K[01]|転|落|沈|妨|失格|失|欠|不)\s+[1-6]\s+\d{4}\b",
                s,
            ):
                candidate_like += 1

            parsed = parse_finish_line(line)
            if parsed:
                entries.append(parsed)
            elif re.match(
                r"^(00|0[1-6]|[1-6]|S[012]|F|L[01]|K[01]|転|落|沈|妨|失格|失|欠|不)\s+[1-6]\s+\d{4}\b",
                s,
            ):
                parse_failed_candidate_lines.append(s)

        by_lane = {}
        for row in entries:
            by_lane.setdefault(row["lane"], row)
        entries = list(by_lane.values())

        normal = sorted(
            [x for x in entries if x["finish_position"] is not None],
            key=lambda x: x["finish_position"],
        )
        finish_order = "-".join(str(x["lane"]) for x in normal) if normal else None

        tri, payout = parse_trifecta(block)

        races.append(
            {
                "race_id": race_id(
                    TARGET_DATE,
                    section["venue_code"],
                    header["race_no"],
                ),
                "venue_code": section["venue_code"],
                "venue_name": section["venue_name"],
                **header,
                "winning_method": method,
                "finish_order": finish_order,
                "entries": entries,
                "candidate_like": candidate_like,
                "parse_failed_candidate_lines": parse_failed_candidate_lines,
                "trifecta_ticket": tri,
                "trifecta_payout": payout,
            }
        )

    return races


def main():
    print(f"✅ audit_k_day_all_pg.py VERSION {VERSION}", flush=True)
    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print("DB書き込みなし。", flush=True)

    text = get_k_text(TARGET_DATE)
    lines = text.splitlines()

    sections = split_venue_sections(lines)

    print("\n=== VENUE SECTIONS ===", flush=True)
    print(f"venue_sections={len(sections)}", flush=True)

    all_races = []

    for section in sections:
        races = parse_section(section)
        all_races.extend(races)

        complete = sum(len(x["entries"]) == 6 for x in races)
        accidents = sum(
            1
            for x in races
            for e in x["entries"]
            if e["finish_position"] is None
        )

        print(
            f"{section['venue_code']}:{section['venue_name']} "
            f"races={len(races)} complete6={complete} accidents={accidents}",
            flush=True,
        )

    # 集計
    race_count = len(all_races)
    complete6 = sum(len(x["entries"]) == 6 for x in all_races)
    entry_rows = sum(len(x["entries"]) for x in all_races)

    trifecta_ok = sum(
        bool(x["trifecta_ticket"]) and bool(x["trifecta_payout"])
        for x in all_races
    )
    method_ok = sum(bool(x["winning_method"]) for x in all_races)
    weather_ok = sum(x["weather"] is not None for x in all_races)
    wind_ok = sum(x["wind_speed_m"] is not None for x in all_races)
    wave_ok = sum(x["wave_height_cm"] is not None for x in all_races)

    exh_rows = sum(
        e["exhibition_time"] is not None
        for x in all_races
        for e in x["entries"]
    )
    course_rows = sum(
        e["start_course"] is not None
        for x in all_races
        for e in x["entries"]
    )
    st_rows = sum(
        e["start_timing"] is not None
        for x in all_races
        for e in x["entries"]
    )

    accident_rows = [
        (x, e)
        for x in all_races
        for e in x["entries"]
        if e["finish_position"] is None
    ]

    parser_fail_lines = [
        (x, line)
        for x in all_races
        for line in x["parse_failed_candidate_lines"]
    ]

    ids = [x["race_id"] for x in all_races]
    duplicate_ids = len(ids) - len(set(ids))

    print("\n=== DAY AUDIT SUMMARY ===", flush=True)
    print(f"races={race_count}", flush=True)
    print(f"entry_rows={entry_rows}", flush=True)
    print(
        f"entries_complete6={complete6}/{race_count} "
        f"pct={(100.0*complete6/race_count if race_count else 0):.2f}%",
        flush=True,
    )
    print(
        f"trifecta_complete={trifecta_ok}/{race_count} "
        f"winning_method_complete={method_ok}/{race_count}",
        flush=True,
    )
    print(
        f"weather_complete={weather_ok}/{race_count} "
        f"wind_complete={wind_ok}/{race_count} "
        f"wave_complete={wave_ok}/{race_count}",
        flush=True,
    )
    print(
        f"exhibition_rows={exh_rows}/{entry_rows} "
        f"course_rows={course_rows}/{entry_rows} "
        f"st_rows={st_rows}/{entry_rows}",
        flush=True,
    )
    print(f"accident_rows={len(accident_rows)}", flush=True)
    print(f"parser_failed_candidate_lines={len(parser_fail_lines)}", flush=True)
    print(f"duplicate_race_ids={duplicate_ids}", flush=True)

    incomplete = [x for x in all_races if len(x["entries"]) != 6]

    if incomplete:
        print("\n=== INCOMPLETE RACE SAMPLE ===", flush=True)
        for x in incomplete[:30]:
            print(
                f"{x['race_id']} {x['venue_name']} {x['race_no']}R "
                f"entries={len(x['entries'])} "
                f"candidate_like={x['candidate_like']} "
                f"tri={x['trifecta_ticket']} payout={x['trifecta_payout']}",
                flush=True,
            )

    if parser_fail_lines:
        print("\n=== PARSER FAILED ROW SAMPLE ===", flush=True)
        for x, line in parser_fail_lines[:30]:
            print(
                f"{x['race_id']} {line!r}",
                flush=True,
            )

    if accident_rows:
        print("\n=== ACCIDENT ROW SAMPLE ===", flush=True)
        for x, e in accident_rows[:30]:
            print(
                f"{x['race_id']} lane={e['lane']} racer={e['racer_number']} "
                f"status={e['finish_status']} course={e['start_course']} "
                f"ST={e['start_timing']}",
                flush=True,
            )

    # PASS条件:
    # - venue section >= 1
    # - duplicate race idなし
    # - parser candidate failureなし
    # - 全レース6艇完全
    # trifecta/決まり手は中止/不成立等があり得るのでPASS必須条件にしない
    passed = (
        len(sections) >= 1
        and duplicate_ids == 0
        and len(parser_fail_lines) == 0
        and complete6 == race_count
        and race_count > 0
    )

    print(
        "\nRESULT=" + ("PASS" if passed else "CHECK"),
        flush=True,
    )


if __name__ == "__main__":
    main()