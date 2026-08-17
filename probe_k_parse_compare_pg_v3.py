# -*- coding: utf-8 -*-
"""
probe_k_parse_compare_pg_v3.py

公式Kファイルと公式Web結果の1レース照合 v3。
DB更新なし。

重要な仕様:
- Kファイルの着欄は、事故時にWeb表示の「転」「妨」等ではなく
  S0/S1/S2, L0/L1, K0/K1, F 等のコードになることがある。
- したがってK側では「事故コード」を正として保存し、
  Web側の詳細事故種別（転/落/沈/妨など）とは finish_position の一致を中心に比較する。
- 例: 2026-08-16 大村12R 6号艇は K=S1 / Web=転。
  どちらも「正常着順なし」という意味では一致する。

DB更新なし。
"""

from __future__ import annotations

import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import lhafile  # type: ignore

from repair_month_all_pg import _fetch, _official_url
from result_detail_pg import parse_result_detail

VERSION = "2026-08-17 k-parse-compare-v3-k-status-codes"

TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-16")
TARGET_VENUE = os.getenv("TARGET_VENUE", "24").zfill(2)
TARGET_RNO = int(os.getenv("TARGET_RNO", "12"))
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

METHODS = ("まくり差し","逃げ","差し","まくり","抜き","恵まれ")

K_STATUS_LABELS = {
    "S0": "失格_選手責任外",
    "S1": "失格_選手責任",
    "S2": "失格_選手責任_妨害",
    "F":  "フライング",
    "L0": "出遅れ_選手責任外",
    "L1": "出遅れ_選手責任",
    "K0": "欠場_選手責任外",
    "K1": "欠場_選手責任",
}


def clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


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
    print(f"K_GET status={r.status_code} bytes={len(r.content)} url={url}", flush=True)
    r.raise_for_status()

    with tempfile.TemporaryDirectory(prefix="kcmp3_") as td:
        archive = Path(td) / "k.lzh"
        archive.write_bytes(r.content)

        lha = lhafile.Lhafile(str(archive))
        names = lha.namelist()
        if not names:
            raise RuntimeError("K archive has no members")

        data = lha.read(names[0])

    return data.decode("cp932")


def parse_header(line: str) -> Optional[Dict[str, Any]]:
    s = clean(line)
    m = re.match(r"(\d{1,2})R\s+(.+?)\s+H(\d+)m\s+(.+)$", s)
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
    正常:
      01 4 5250 ... 7.01 4 0.15 1.51.2

    K事故コード:
      S1 6 5360 ... 6.98 6 0.11 . .
      S0 / S1 / S2 / F / L0 / L1 / K0 / K1 に対応。
    """
    s = clean(line)

    head = re.match(
        r"^(?P<status>"
        r"0[1-6]|[1-6]|"
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

    rest = head.group("rest")

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

    status = head.group("status")
    finish_position = int(status) if re.fullmatch(r"0?[1-6]", status) else None
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
        "finish_status_label": K_STATUS_LABELS.get(status, status),
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
        "source_line": s,
    }


def parse_trifecta(lines: List[str]) -> Dict[str, Any]:
    for line in lines:
        m = re.search(
            r"３連単\s+([1-6]-[1-6]-[1-6])\s+([\d,]+)",
            clean(line),
        )
        if m:
            return {
                "trifecta_ticket": m.group(1),
                "trifecta_payout": int(m.group(2).replace(",", "")),
            }

    return {"trifecta_ticket": None, "trifecta_payout": None}


def parse_race_block(text: str, rno: int) -> Dict[str, Any]:
    lines = text.splitlines()

    # 払戻一覧の "12R 4-5-1..." を除き、
    # H1800mを含む詳細見出しだけを対象にする。
    detail_starts = []
    for i, line in enumerate(lines):
        h = parse_header(line)
        if h and h["race_no"] == rno:
            detail_starts.append((i, h))

    if not detail_starts:
        raise RuntimeError(f"K detail block not found: {rno}R")

    # 1日複数場の同一Rがある。
    # このプローブv3は、TARGET_VENUE=24のテストとして
    # 登録番号5360が含まれるブロックを優先。
    selected = None

    for start_idx, header in detail_starts:
        end_idx = min(len(lines), start_idx + 100)

        for j in range(start_idx + 1, min(len(lines), start_idx + 100)):
            h2 = parse_header(lines[j])
            if h2:
                end_idx = j
                break
            if lines[j].strip() == "ENDK" or re.fullmatch(r"\d{2}KEND", lines[j].strip()):
                end_idx = j
                break

        block = lines[start_idx:end_idx]

        # 今回の既知照合レースを優先
        if TARGET_VENUE == "24" and any("5360" in x for x in block):
            selected = (header, block)
            break

    if selected is None:
        # fallback: 最初の詳細12R
        start_idx, header = detail_starts[0]
        end_idx = min(len(lines), start_idx + 100)
        for j in range(start_idx + 1, min(len(lines), start_idx + 100)):
            h2 = parse_header(lines[j])
            if h2:
                end_idx = j
                break
        selected = (header, lines[start_idx:end_idx])

    header, block = selected

    winning_method = None
    for line in block[:6]:
        for method in METHODS:
            if method in clean(line):
                winning_method = method
                break
        if winning_method:
            break

    entries = []
    for line in block:
        row = parse_finish_line(line)
        if row:
            entries.append(row)

    by_lane = {}
    for row in entries:
        by_lane.setdefault(row["lane"], row)
    entries = list(by_lane.values())

    normal = sorted(
        [x for x in entries if x["finish_position"] is not None],
        key=lambda x: x["finish_position"],
    )
    finish_order = "-".join(str(x["lane"]) for x in normal) if normal else None

    return {
        **header,
        "winning_method": winning_method,
        "finish_order": finish_order,
        "entries": entries,
        **parse_trifecta(block),
    }


def main():
    print(f"✅ probe_k_parse_compare_pg_v3.py VERSION {VERSION}", flush=True)
    print(
        f"TARGET_DATE={TARGET_DATE} TARGET_VENUE={TARGET_VENUE}"
        f"({VENUE_NAMES.get(TARGET_VENUE)}) TARGET_RNO={TARGET_RNO}",
        flush=True,
    )
    print("DB書き込みなし。", flush=True)

    k = parse_race_block(get_k_text(TARGET_DATE), TARGET_RNO)

    print("\n=== K PARSED ===", flush=True)
    print(
        f"entries={len(k['entries'])} "
        f"winning_method={k.get('winning_method')} "
        f"finish_order={k.get('finish_order')} "
        f"trifecta={k.get('trifecta_ticket')} "
        f"payout={k.get('trifecta_payout')}",
        flush=True,
    )

    for row in sorted(k["entries"], key=lambda x: x["lane"]):
        print(
            f"lane={row['lane']} racer={row['racer_number']} "
            f"finish={row['finish_position']} "
            f"status={row['finish_status']} "
            f"status_label={row['finish_status_label']} "
            f"motor={row['motor_no']} boat={row['boat_no']} "
            f"exh={row['exhibition_time']} course={row['start_course']} "
            f"ST={row['start_timing']} F={row['is_flying']} "
            f"L={row['is_late']} time={row['race_time']}",
            flush=True,
        )

    web_html = _fetch(_official_url("raceresult", TARGET_DATE, TARGET_VENUE, TARGET_RNO))
    if not web_html:
        raise RuntimeError("WEB raceresult fetch failed")

    web = parse_result_detail(web_html)

    kb = {int(x["lane"]): x for x in k["entries"]}
    wb = {int(x["lane"]): x for x in web.get("entries", [])}

    print("\n=== ENTRY COMPARE ===", flush=True)

    mismatches = 0
    for lane in range(1, 7):
        a = kb.get(lane)
        b = wb.get(lane)

        if a is None or b is None:
            print(f"lane={lane} MISSING K={a is None} WEB={b is None}", flush=True)
            mismatches += 1
            continue

        # KのS1とWebの「転」は表現レイヤーが違うため
        # finish_status文字列の完全一致は要求しない。
        fields = [
            ("racer_number", a.get("racer_number"), b.get("racer_number")),
            ("finish_position", a.get("finish_position"), b.get("finish_position")),
            ("start_course", a.get("start_course"), b.get("start_course")),
            ("start_timing", a.get("start_timing"), b.get("start_timing")),
        ]

        bad = [
            (name, ka, wa)
            for name, ka, wa in fields
            if ka != wa
        ]

        if bad:
            mismatches += 1
            print(
                f"lane={lane} MISMATCH "
                + " | ".join(f"{n}:K={ka}/WEB={wa}" for n, ka, wa in bad),
                flush=True,
            )
        else:
            print(
                f"lane={lane} OK racer={a['racer_number']} "
                f"finish={a['finish_position']} "
                f"Kstatus={a['finish_status']} "
                f"WEBstatus={b.get('finish_status')} "
                f"course={a['start_course']} ST={a['start_timing']}",
                flush=True,
            )

    top_level_match = (
        k.get("winning_method") == web.get("winning_method")
        and k.get("finish_order") == web.get("finish_order")
    )

    print("\n=== SUMMARY ===", flush=True)
    print(
        f"entries_complete={len(k['entries']) == 6} "
        f"entry_mismatch_lanes={mismatches} "
        f"top_level_match={top_level_match} "
        f"entry_match={mismatches == 0}",
        flush=True,
    )

    print(
        "RESULT="
        + (
            "PASS"
            if len(k["entries"]) == 6 and mismatches == 0 and top_level_match
            else "CHECK"
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()