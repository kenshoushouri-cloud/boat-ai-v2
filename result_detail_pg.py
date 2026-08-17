# -*- coding: utf-8 -*-
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

WINNING_METHODS = ("まくり差し", "逃げ", "差し", "まくり", "抜き", "恵まれ")

def _clean(v: Any) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()

def _zen_to_han(s: str) -> str:
    trans = str.maketrans({"０":"0","１":"1","２":"2","３":"3","４":"4","５":"5","６":"6","７":"7","８":"8","９":"9","．":".","－":"-","　":" ","：":":"})
    return str(s or "").translate(trans)

def _rank_value(text: str) -> Optional[int]:
    s = _zen_to_han(_clean(text))
    m = re.fullmatch(r"([1-6])", s)
    return int(m.group(1)) if m else None

def _is_result_status(text: str) -> bool:
    s = _zen_to_han(_clean(text))
    if re.fullmatch(r"[1-6]", s):
        return True
    return s in {"F","L","欠","欠場","失","失格","落","転","沈","不","妨","エ","責","即","返"}

def parse_winning_method(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    text = _clean(soup.get_text(" ", strip=True))
    m = re.search(r"決まり手.{0,40}?(まくり差し|逃げ|差し|まくり|抜き|恵まれ)", text)
    return m.group(1) if m else None

def _parse_finish_rows(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    rows, seen = [], set()
    for tr in soup.find_all("tr"):
        cells = [_clean(_zen_to_han(x.get_text(" ", strip=True))) for x in tr.find_all(["td","th"])]
        if len(cells) < 3:
            continue
        status, lane_text = cells[0], cells[1]
        if not _is_result_status(status) or not re.fullmatch(r"[1-6]", lane_text):
            continue
        lane = int(lane_text)
        if lane in seen:
            continue
        m = re.search(r"\b(\d{4})\b\s*(.*)", cells[2])
        racer_number = int(m.group(1)) if m else None
        racer_name = _clean(m.group(2)) if m and _clean(m.group(2)) else None
        rows.append({
            "display_order": len(rows)+1,
            "finish_position": _rank_value(status),
            "finish_status": status,
            "lane": lane,
            "racer_number": racer_number,
            "racer_name": racer_name,
            "race_time": cells[3] if len(cells) >= 4 and cells[3] else None,
        })
        seen.add(lane)
        if len(rows) == 6:
            break
    return rows

def _extract_start_segment(soup: BeautifulSoup) -> str:
    lines = [_clean(_zen_to_han(x)) for x in soup.get_text("\n", strip=True).splitlines()]
    lines = [x for x in lines if x]
    try:
        start = next(i for i,x in enumerate(lines) if "スタート情報" in x)
    except StopIteration:
        return ""
    end = len(lines)
    for i in range(start+1, len(lines)):
        if any(w in lines[i] for w in ("勝式","組番","払戻金","水面気象情報","返還","決まり手")):
            end = i
            break
    return " ".join(lines[start+1:end])

def _parse_start_rows(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    segment = _extract_start_segment(soup)
    if not segment:
        return []
    token_re = re.compile(r"(?<!\d)([1-6])\s+(?:(F|L)\s*)?([+-]?(?:0?\.)?\d{2})(?!\d)")
    out, seen = [], set()
    for m in token_re.finditer(segment):
        lane = int(m.group(1))
        if lane in seen:
            continue
        flag, raw_num = m.group(2), m.group(3)
        try:
            st = float(raw_num) if "." in raw_num else int(raw_num)/100.0
        except Exception:
            st = None
        out.append({
            "lane": lane,
            "start_course": len(out)+1,
            "start_timing": st,
            "start_status": flag,
            "is_flying": flag == "F",
            "is_late": flag == "L",
            "start_timing_raw": f"{flag or ''}{raw_num}",
        })
        seen.add(lane)
        if len(out) == 6:
            break
    if len(out) != 6:
        for row in out:
            row["start_course"] = None
    return out

def parse_result_detail(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    finish_rows = _parse_finish_rows(soup)
    start_rows = _parse_start_rows(soup)
    winning_method = parse_winning_method(html)
    start_by_lane = {int(x["lane"]): x for x in start_rows}
    entries = []
    for f in finish_rows:
        s = start_by_lane.get(int(f["lane"]), {})
        entries.append({
            **f,
            "start_course": s.get("start_course"),
            "start_timing": s.get("start_timing"),
            "start_status": s.get("start_status"),
            "is_flying": bool(s.get("is_flying", False)),
            "is_late": bool(s.get("is_late", False)),
            "start_timing_raw": s.get("start_timing_raw"),
        })
    normal = [x for x in entries if x.get("finish_position") is not None]
    normal.sort(key=lambda x: int(x["finish_position"]))
    finish_order = "-".join(str(x["lane"]) for x in normal) if normal else None
    return {
        "winning_method": winning_method,
        "finish_order": finish_order,
        "entries": entries,
        "finish_rows_count": len(finish_rows),
        "start_rows_count": len(start_rows),
        "start_course_complete": len(start_rows) == 6,
        "raw": {"finish_entries": entries, "winning_method": winning_method, "finish_order": finish_order},
    }