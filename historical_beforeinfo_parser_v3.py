# -*- coding: utf-8 -*-
"""Historical BOAT RACE beforeinfo parser helpers.

This module is intentionally isolated from the production realtime collector.
It is used first by historical backfill/replay so parser changes can be
validated before any Production FINAL input path is changed.

VERSION: 2026-08-22 historical-beforeinfo-parser-v3
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

VERSION = "2026-08-22 historical-beforeinfo-parser-v3"


def _norm(value: Any) -> str:
    return re.sub(
        r"\s+",
        " ",
        unicodedata.normalize("NFKC", str(value or "")),
    ).strip()


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        text = _norm(value).replace(",", "")
        if text.startswith("."):
            text = "0" + text
        if text.startswith("-."):
            text = text.replace("-.", "-0.", 1)
        return float(text)
    except Exception:
        return None


def _direct_cells(tr) -> List[str]:
    return [
        _norm(c.get_text(" ", strip=True))
        for c in tr.find_all(["th", "td"], recursive=False)
    ]


def _lane_from_cells(cells: List[str]) -> Optional[int]:
    for value in cells[:3]:
        if re.fullmatch(r"[1-6]", value):
            return int(value)
    return None


def _parse_primary_boat_rows(soup: BeautifulSoup) -> Dict[int, Dict[str, Any]]:
    """Parse per-boat exhibition time and tilt from the primary beforeinfo rows.

    BOAT RACE's current beforeinfo table is laid out as:
      lane / image / racer / weight / exhibition_time / tilt / propeller /
      parts / previous-race...

    We still validate the numeric shapes instead of trusting values blindly.
    """
    out: Dict[int, Dict[str, Any]] = {}

    for tbody in soup.select("tbody.is-fs12"):
        trs = tbody.find_all("tr", recursive=False)
        if not trs:
            continue
        cells = _direct_cells(trs[0])
        lane = _lane_from_cells(cells)
        if lane is None:
            continue

        exhibition_time = None
        tilt = None

        # Preferred structural positions observed on official beforeinfo pages.
        if len(cells) >= 6:
            t = _safe_float(cells[4])
            if t is not None and 6.0 <= t < 8.0:
                exhibition_time = t
            z = _safe_float(cells[5])
            if z is not None and -3.0 <= z <= 3.0:
                tilt = z

        # Defensive fallback: find a 6.xx/7.xx time, then the first plausible
        # tilt value after it. This tolerates harmless markup-column changes.
        if exhibition_time is None:
            time_idx = None
            for idx, cell in enumerate(cells):
                if re.fullmatch(r"[67]\.\d{2}", cell):
                    exhibition_time = _safe_float(cell)
                    time_idx = idx
                    break
            if time_idx is not None and tilt is None:
                for cell in cells[time_idx + 1 :]:
                    if re.fullmatch(r"[-+]?\d(?:\.\d)?", cell):
                        z = _safe_float(cell)
                        if z is not None and -3.0 <= z <= 3.0:
                            tilt = z
                            break

        if exhibition_time is None:
            continue

        out[lane] = {
            "lane": lane,
            "exhibition_course": lane,
            "exhibition_time": exhibition_time,
            "start_timing": None,
            "tilt": tilt,
            "raw_cells": [cells],
        }

    return out


def _parse_start_exhibition(text: str) -> List[Tuple[int, float]]:
    """Return [(boat/lane, ST), ...] in *course order*.

    Official pages render the start-display rows in course order. For example:
      2 Image .01 / 1 Image .03 / 3 Image .07 ...
    means boat 2 took course 1 and boat 1 took course 2.

    F/L marks are intentionally handled compatibly with the current realtime
    collector: the numeric magnitude is retained. This parser change does not
    alter the existing ST-sign semantics.
    """
    start = text.find("スタート展示")
    if start < 0:
        return []
    end = text.find("水面気象情報", start)
    segment = text[start : end if end >= 0 else None]

    pairs: List[Tuple[int, float]] = []
    # BeautifulSoup omits image pixels but may preserve image alt text as
    # "Image" in some rendered/cached representations, so tolerate both.
    pattern = re.compile(
        r"(?<!\d)([1-6])\s*(?:Image\s*)?([FL]?\s*\.?\d{2})(?!\d)",
        flags=re.I,
    )
    for match in pattern.finditer(segment):
        lane = int(match.group(1))
        raw_st = match.group(2).upper().replace(" ", "")
        numeric = raw_st.replace("F", "").replace("L", "")
        st = _safe_float(numeric)
        if st is None or not (0.0 <= st <= 0.99):
            continue
        if lane in {x[0] for x in pairs}:
            continue
        pairs.append((lane, st))
        if len(pairs) == 6:
            break

    if len(pairs) != 6 or {lane for lane, _ in pairs} != set(range(1, 7)):
        return []
    return pairs


def _rank_diff(rows: List[Dict[str, Any]], key: str, rank_key: str, diff_key: str) -> None:
    values = sorted(
        [
            (int(row["lane"]), float(row[key]))
            for row in rows
            if row.get(key) is not None
        ],
        key=lambda item: item[1],
    )
    if not values:
        return
    best = values[0][1]
    ranks = {lane: idx + 1 for idx, (lane, _) in enumerate(values)}
    for row in rows:
        if row.get(key) is None:
            continue
        lane = int(row["lane"])
        row[rank_key] = ranks[lane]
        row[diff_key] = round(float(row[key]) - best, 3)


def _fallback_times(text: str) -> Dict[int, Dict[str, Any]]:
    """Compatibility fallback for pages whose primary table markup changed."""
    before_start = text.split("スタート展示", 1)[0]
    times = [
        _safe_float(x)
        for x in re.findall(r"(?<!\d)([67]\.\d{2})(?!\d)", before_start)
    ]
    times = [x for x in times if x is not None][:6]
    if len(times) != 6:
        return {}
    return {
        lane: {
            "lane": lane,
            "exhibition_course": lane,
            "exhibition_time": times[lane - 1],
            "start_timing": None,
            "tilt": None,
            "raw_cells": [],
        }
        for lane in range(1, 7)
    }


def parse_exhibition(html: str) -> List[Dict[str, Any]]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    text = _norm(soup.get_text(" ", strip=True))

    by_lane = _parse_primary_boat_rows(soup)
    if len(by_lane) != 6:
        by_lane = _fallback_times(text)
    if len(by_lane) != 6:
        return []

    start_pairs = _parse_start_exhibition(text)
    if start_pairs:
        for course, (lane, st) in enumerate(start_pairs, 1):
            row = by_lane.get(lane)
            if row is None:
                return []
            row["exhibition_course"] = course
            row["start_timing"] = st

    rows = [by_lane[lane] for lane in range(1, 7)]
    _rank_diff(rows, "exhibition_time", "exhibition_time_rank", "exhibition_time_diff")
    _rank_diff(rows, "start_timing", "start_timing_rank", "start_timing_diff")
    return rows
