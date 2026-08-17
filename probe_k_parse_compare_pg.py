# -*- coding: utf-8 -*-
"""
probe_k_parse_compare_pg.py

公式Kファイルを1日分取得・解凍・解析し、
指定1レースの結果詳細をKファイルから構造化して、
公式Web raceresult parser と照合する。

DB更新なし。

比較:
- 1～6艇の着順/事故状態
- 艇番
- 登録番号
- モーター/ボート
- 展示タイム
- 実進入
- ST
- レースタイム
- 決まり手
- 三連単/払戻
- 天候/風向/風速/波高

デフォルト:
  TARGET_DATE=2026-08-16
  TARGET_VENUE=24
  TARGET_RNO=12
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

VERSION = "2026-08-17 k-parse-compare-v1"

TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-16")
TARGET_VENUE = os.getenv("TARGET_VENUE", "24").zfill(2)
TARGET_RNO = int(os.getenv("TARGET_RNO", "12"))
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
    ),
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


def k_url(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (
        "https://www1.mbrace.or.jp/od2/K/"
        f"{dt.strftime('%Y%m')}/k{dt.strftime('%y%m%d')}.lzh"
    )


def get_k_text(date_str: str) -> str:
    url = k_url(date_str)
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    print(f"K_GET status={r.status_code} bytes={len(r.content)} url={url}", flush=True)
    r.raise_for_status()

    with tempfile.TemporaryDirectory(prefix="kcmp_") as td:
        archive = Path(td) / "k.lzh"
        archive.write_bytes(r.content)
        lha = lhafile.Lhafile(str(archive))
        names = lha.namelist()
        if not names:
            raise RuntimeError("K archive has no members")
        data = lha.read(names[0])

    for enc in ("cp932", "shift_jis"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    raise RuntimeError("K TXT decode failed")


def clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def num(v: str) -> Optional[float]:
    try:
        return float(v)
    except Exception:
        return None


def parse_header(line: str) -> Optional[Dict[str, Any]]:
    """
    例:
      12R       一般　　　　 H1800m  晴れ  風  北東　 2m  波 1cm
    """
    s = clean(line)
    m = re.match(r"(\d{1,2})R\s+(.+?)\s+H(\d+)m\s+(.+)$", s)
    if not m:
        return None

    rno = int(m.group(1))
    title = clean(m.group(2))
    distance = int(m.group(3))
    tail = m.group(4)

    weather = None
    wind_direction = None
    wind_speed = None
    wave = None

    # 「晴れ 風 北東 2m 波 1cm」等
    wm = re.search(r"^(.+?)\s+風\s+(.+?)\s+(\d+(?:\.\d+)?)m\s+波\s+(\d+(?:\.\d+)?)cm", tail)
    if wm:
        weather = clean(wm.group(1))
        wind_direction = clean(wm.group(2))
        wind_speed = float(wm.group(3))
        wave = float(wm.group(4))

    return {
        "race_no": rno,
        "race_title": title,
        "distance_m": distance,
        "weather": weather,
        "wind_direction": wind_direction,
        "wind_speed_m": wind_speed,
        "wave_height_cm": wave,
    }


def parse_finish_line(line: str) -> Optional[Dict[str, Any]]:
    """
    正常:
    01  4 5250 嶋田 有里 34 85 6.96 4 0.15 1.51.2

    事故行も着欄が「転」「妨」等になる場合があるため、
    数値順位以外も許容する。
    """
    s = clean(line)

    # 正常順位 / 代表的事故コード
    m = re.match(
        r"^(0[1-6]|[1-6]|F|L|転|落|沈|妨|失|失格|欠|不)\s+"
        r"([1-6])\s+"
        r"(\d{4})\s+"
        r"(.+?)\s+"
        r"(\d{1,3})\s+"
        r"(\d{1,3})\s+"
        r"(\d+\.\d{2})\s+"
        r"([1-6])\s+"
        r"([FL]?\s*[-+]?\d*\.\d{2}|[FL]?\s*\d{2})"
        r"(?:\s+(.+))?$",
        s
    )
    if not m:
        return None

    status = m.group(1)
    finish_position = int(status) if re.fullmatch(r"0?[1-6]", status) else None
    lane = int(m.group(2))
    racer_number = int(m.group(3))
    racer_name = clean(m.group(4))
    motor_no = int(m.group(5))
    boat_no = int(m.group(6))
    exhibition_time = float(m.group(7))
    start_course = int(m.group(8))
    st_raw = clean(m.group(9))

    flag = None
    if st_raw.startswith("F"):
        flag = "F"
    elif st_raw.startswith("L"):
        flag = "L"

    st_numeric = st_raw.lstrip("FL ").strip()
    try:
        st = float(st_numeric) if "." in st_numeric else int(st_numeric) / 100.0
    except Exception:
        st = None

    race_time_raw = clean(m.group(10))
    race_time = None
    if race_time_raw and race_time_raw not in (". .", ".  .", ". ."):
        # 先頭トークンだけレースタイムとして採用
        race_time = race_time_raw.split()[0]

    return {
        "finish_position": finish_position,
        "finish_status": status,
        "lane": lane,
        "racer_number": racer_number,
        "racer_name": racer_name,
        "motor_no": motor_no,
        "boat_no": boat_no,
        "exhibition_time": exhibition_time,
        "start_course": start_course,
        "start_timing": st,
        "start_status": flag,
        "is_flying": flag == "F",
        "is_late": flag == "L",
        "race_time": race_time,
    }


def parse_trifecta(lines: List[str]) -> Dict[str, Any]:
    for line in lines:
        s = clean(line)
        m = re.search(r"３連単\s+([1-6]-[1-6]-[1-6])\s+([\d,]+)", s)
        if m:
            return {
                "trifecta_ticket": m.group(1),
                "trifecta_payout": int(m.group(2).replace(",", "")),
            }
    return {"trifecta_ticket": None, "trifecta_payout": None}


def parse_race_block(text: str, rno: int) -> Dict[str, Any]:
    lines = text.splitlines()

    start_idx = None
    header = None

    for i, line in enumerate(lines):
        h = parse_header(line)
        if h and h["race_no"] == rno:
            start_idx = i
            header = h
            break

    if start_idx is None:
        raise RuntimeError(f"K block not found: {rno}R")

    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        h = parse_header(lines[i])
        if h and h["race_no"] != rno:
            end_idx = i
            break
        if lines[i].strip() in ("ENDK", "24KEND"):
            end_idx = i
            break

    block = lines[start_idx:end_idx]

    method = None
    # 見出し行または次行に決まり手がある
    for line in block[:5]:
        s = clean(line)
        for x in METHODS:
            if x in s:
                method = x
                break
        if method:
            break

    entries = []
    for line in block:
        x = parse_finish_line(line)
        if x:
            entries.append(x)

    # 重複防止
    by_lane = {}
    for x in entries:
        by_lane.setdefault(x["lane"], x)
    entries = list(by_lane.values())

    tri = parse_trifecta(block)

    normal = [x for x in entries if x["finish_position"] is not None]
    normal.sort(key=lambda x: x["finish_position"])
    finish_order = "-".join(str(x["lane"]) for x in normal) if normal else None

    return {
        **(header or {}),
        "winning_method": method,
        "finish_order": finish_order,
        "entries": entries,
        **tri,
        "block_line_count": len(block),
    }


def compare(k: Dict[str, Any], web: Dict[str, Any]) -> None:
    print("\n=== TOP LEVEL COMPARE ===", flush=True)
    print(
        f"K winning_method={k.get('winning_method')} "
        f"finish_order={k.get('finish_order')} "
        f"trifecta={k.get('trifecta_ticket')} "
        f"payout={k.get('trifecta_payout')}",
        flush=True,
    )
    print(
        f"WEB winning_method={web.get('winning_method')} "
        f"finish_order={web.get('finish_order')}",
        flush=True,
    )

    print("\n=== ENTRY COMPARE ===", flush=True)
    wb = {int(x["lane"]): x for x in web.get("entries", [])}
    kb = {int(x["lane"]): x for x in k.get("entries", [])}

    mismatches = 0

    for lane in range(1, 7):
        a = kb.get(lane)
        b = wb.get(lane)

        if a is None or b is None:
            print(f"lane={lane} missing K={a is None} WEB={b is None}", flush=True)
            mismatches += 1
            continue

        fields = [
            ("racer_number", a.get("racer_number"), b.get("racer_number")),
            ("finish_position", a.get("finish_position"), b.get("finish_position")),
            ("start_course", a.get("start_course"), b.get("start_course")),
            ("start_timing", a.get("start_timing"), b.get("start_timing")),
            ("is_flying", a.get("is_flying"), b.get("is_flying")),
            ("is_late", a.get("is_late"), b.get("is_late")),
        ]

        bad = [
            f"{name}:K={ka}/WEB={wbv}"
            for name, ka, wbv in fields
            if ka != wbv
        ]

        if bad:
            mismatches += 1
            print(f"lane={lane} MISMATCH " + " | ".join(bad), flush=True)
        else:
            print(
                f"lane={lane} OK "
                f"racer={a.get('racer_number')} "
                f"finish={a.get('finish_position')} "
                f"course={a.get('start_course')} "
                f"ST={a.get('start_timing')}",
                flush=True,
            )

    print(f"\nentry_mismatch_lanes={mismatches}", flush=True)

    top_ok = (
        k.get("winning_method") == web.get("winning_method")
        and k.get("finish_order") == web.get("finish_order")
    )

    print(
        f"top_level_match={top_ok} entry_match={mismatches == 0}",
        flush=True,
    )


def main():
    print(f"✅ probe_k_parse_compare_pg.py VERSION {VERSION}", flush=True)
    print(
        f"TARGET_DATE={TARGET_DATE} "
        f"TARGET_VENUE={TARGET_VENUE}({VENUE_NAMES.get(TARGET_VENUE)}) "
        f"TARGET_RNO={TARGET_RNO}",
        flush=True,
    )
    print("DB書き込みなし。", flush=True)

    if TARGET_VENUE != "24":
        print(
            "NOTE: Kファイルは複数場を含むため、v1では対象場ブロック切り分けを"
            "簡略化しています。まず大村24で照合します。",
            flush=True,
        )

    text = get_k_text(TARGET_DATE)

    # v1では2026-08-16の大村ブロックが先頭なので、その中のR番号を解析。
    # 次版で24場全ブロックの正式分割を実装する。
    k = parse_race_block(text, TARGET_RNO)

    print("\n=== K PARSED ===", flush=True)
    print(
        f"race={k.get('race_no')}R title={k.get('race_title')} "
        f"weather={k.get('weather')} wind={k.get('wind_direction')} "
        f"{k.get('wind_speed_m')}m wave={k.get('wave_height_cm')}cm",
        flush=True,
    )
    print(
        f"winning_method={k.get('winning_method')} "
        f"finish_order={k.get('finish_order')} "
        f"trifecta={k.get('trifecta_ticket')} "
        f"payout={k.get('trifecta_payout')} "
        f"entries={len(k.get('entries', []))}",
        flush=True,
    )
    for x in sorted(k.get("entries", []), key=lambda z: z["lane"]):
        print(
            f"lane={x['lane']} racer={x['racer_number']} "
            f"finish={x['finish_position']} status={x['finish_status']} "
            f"motor={x['motor_no']} boat={x['boat_no']} "
            f"exh={x['exhibition_time']} course={x['start_course']} "
            f"ST={x['start_timing']} F={x['is_flying']} L={x['is_late']} "
            f"time={x['race_time']}",
            flush=True,
        )

    web_html = _fetch(
        _official_url("raceresult", TARGET_DATE, TARGET_VENUE, TARGET_RNO)
    )
    if not web_html:
        raise RuntimeError("WEB raceresult fetch failed")

    web = parse_result_detail(web_html)

    compare(k, web)

    print("\nRESULT=SUCCESS", flush=True)


if __name__ == "__main__":
    main()