# -*- coding: utf-8 -*-
"""Side-effect-free BOAT RACE official trifecta odds parser.

The current official page renders trifecta odds as a table whose extracted text
is not a contiguous ``1-2-3 12.4`` sequence.  This module recognizes that table
layout, emits only canonical 1..6 three-lane permutations, and never fabricates
missing tickets.
"""
from __future__ import annotations

import math
import re
from html.parser import HTMLParser
from typing import Mapping

CANONICAL_TICKETS = tuple(
    f"{a}-{b}-{c}"
    for a in range(1, 7)
    for b in range(1, 7)
    if b != a
    for c in range(1, 7)
    if c not in (a, b)
)
CANONICAL_SET = frozenset(CANONICAL_TICKETS)
assert len(CANONICAL_TICKETS) == 120 and len(CANONICAL_SET) == 120


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data and data.strip():
            self.parts.append(data.strip())


def _text_lines(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return ""
    return "\n".join(parser.parts)


def _lane_token(token: str, value: int) -> bool:
    return bool(re.fullmatch(r"[1-6]", token or "")) and int(token) == value


def _clean_odds(values: Mapping[str, object] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for raw_ticket, raw_value in (values or {}).items():
        ticket = str(raw_ticket or "").strip()
        if ticket not in CANONICAL_SET:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and value > 0:
            out[ticket] = value
    return out


def is_complete_snapshot(values: Mapping[str, object] | None) -> bool:
    cleaned = _clean_odds(values)
    return len(cleaned) == 120 and set(cleaned) == CANONICAL_SET


def parse_official_odds3t(html: str) -> dict[str, float]:
    """Parse current official table layout, then legacy contiguous ticket text.

    The table parser is intentionally structural and bounded to one 270-token
    3T table.  If the layout cannot be recognized, a legacy contiguous-ticket
    parser is attempted for compatibility with older fixtures/pages.
    """
    if not isinstance(html, str) or not html:
        return {}

    text_lines = _text_lines(html)
    if not text_lines:
        return {}
    segment = (
        text_lines.split("3連単オッズ", 1)[1]
        if "3連単オッズ" in text_lines
        else text_lines
    )
    for marker in ("締切時オッズは", "レース開始後", "PAGE TOP"):
        if marker in segment:
            segment = segment.split(marker, 1)[0]

    tokens = re.findall(r"\d+(?:\.\d+)?", segment)
    firsts = (1, 2, 3, 4, 5, 6)
    expected: list[tuple[int, int]] = []
    for first in firsts:
        second = next(x for x in firsts if x != first)
        third = next(x for x in firsts if x not in (first, second))
        expected.append((second, third))

    start = None
    needed = 270
    for i in range(max(0, len(tokens) - needed + 1)):
        if all(
            _lane_token(tokens[i + col * 3], second)
            and _lane_token(tokens[i + col * 3 + 1], third)
            for col, (second, third) in enumerate(expected)
        ):
            start = i
            break

    if start is not None:
        out: dict[str, float] = {}
        idx = start
        try:
            for second_group in range(5):
                second_by_first = {
                    first: [x for x in firsts if x != first][second_group]
                    for first in firsts
                }
                for third_row in range(4):
                    for first in firsts:
                        second = second_by_first[first]
                        if third_row == 0:
                            second_token = tokens[idx]
                            third_token = tokens[idx + 1]
                            odd_token = tokens[idx + 2]
                            idx += 3
                            if not _lane_token(second_token, second):
                                return {}
                        else:
                            third_token = tokens[idx]
                            odd_token = tokens[idx + 1]
                            idx += 2
                        if not re.fullmatch(r"[1-6]", third_token or ""):
                            return {}
                        third = int(third_token)
                        if len({first, second, third}) != 3:
                            return {}
                        odd = float(odd_token)
                        if not math.isfinite(odd) or odd <= 0:
                            return {}
                        ticket = f"{first}-{second}-{third}"
                        if ticket not in CANONICAL_SET or ticket in out:
                            return {}
                        out[ticket] = odd
        except (IndexError, TypeError, ValueError):
            return {}
        if len(out) == 120 and set(out) == CANONICAL_SET:
            return out
        return {}

    legacy: dict[str, float] = {}
    for match in re.finditer(
        r"([1-6])\s*[-－]\s*([1-6])\s*[-－]\s*([1-6])\s+"
        r"([0-9]{1,4}(?:\.[0-9])?)",
        segment,
    ):
        a, b, c, raw_odd = match.groups()
        if len({a, b, c}) != 3:
            continue
        ticket = f"{a}-{b}-{c}"
        try:
            odd = float(raw_odd)
        except ValueError:
            continue
        if ticket in CANONICAL_SET and math.isfinite(odd) and odd > 0:
            legacy[ticket] = odd
    return legacy


def choose_realtime_snapshot(
    official_values: Mapping[str, object] | None,
    base_values: Mapping[str, object] | None,
) -> tuple[dict[str, float], str]:
    """Choose a realtime odds set without propagating incomplete base data.

    Direct official data wins only when it is exactly the canonical 120-ticket
    set.  The legacy base-table fallback is permitted only when that base set is
    itself exactly complete.  Otherwise the collector must fail closed and skip
    an odds snapshot instead of copying a partial set into realtime storage.
    """
    official = _clean_odds(official_values)
    if len(official) == 120 and set(official) == CANONICAL_SET:
        return official, "official_odds3t"
    base = _clean_odds(base_values)
    if len(base) == 120 and set(base) == CANONICAL_SET:
        return base, "v2_odds_trifecta_fallback"
    return {}, "unavailable_incomplete"
