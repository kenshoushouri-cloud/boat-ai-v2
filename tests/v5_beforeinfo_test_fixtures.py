# -*- coding: utf-8 -*-
"""Synthetic six-boat official-style beforeinfo fixtures; NOT real observations."""
from __future__ import annotations

import hashlib

URL = "https://www.boatrace.jp/owpc/pc/race/beforeinfo?rno=4&jcd=09&hd=20261010"
RACELIST_URL = "https://www.boatrace.jp/owpc/pc/race/racelist?rno=4&jcd=09&hd=20261010"
RACE = "20261010_09_04"
START = "2026-10-10T11:49:59+09:00"
CAPTURE = "2026-10-10T11:50:00+09:00"
CUTOFF = "2026-10-10T11:55:00+09:00"
DEADLINE = "2026-10-10T12:00:00+09:00"


def six_boat_html(*, variation: str = "", omit_lane: int | None = None,
                  duplicate_lane: int | None = None,
                  missing_time_lane: int | None = None) -> bytes:
    """Structured rows accepted by the existing strict per-boat parser."""
    tbodies = []
    for lane in range(1, 7):
        if lane == omit_lane:
            continue
        time = "" if lane == missing_time_lane else f"{6.70 + lane / 100:.2f}"
        tbodies.append(
            f'<tbody class="is-fs12"><tr><td>{lane}</td><td></td>'
            f'<td>選手{lane}</td><td>52.0kg</td><td>{time}</td>'
            '<td>0.0</td><td></td><td></td></tr></tbody>'
        )
    if duplicate_lane is not None:
        tbodies.append(
            f'<tbody class="is-fs12"><tr><td>{duplicate_lane}</td><td></td>'
            '<td>二重行</td><td>52.0kg</td><td>6.88</td><td>0.0</td>'
            '<td></td><td></td></tr></tbody>'
        )
    # Only used to distinguish two otherwise complete captures. Does not
    # introduce hidden runner metadata or post-race result information.
    return (
        '<html><body><table>' + ''.join(tbodies) + '</table>'
        '<h3>水面気象情報</h3><p>気温20℃ 水温18℃</p>'
        f'<!-- {variation} --></body></html>'
    ).encode("utf-8")


def racelist_evidence():
    # Claimed verified first-write credentials below are synthetic assertions.
    # This fixture NEVER proves actual official/source authenticity.
    return {
        "source": "official_racelist",
        "race_id": RACE,
        "source_url": RACELIST_URL,
        "captured_at": "2026-10-10T11:48:00+09:00",
        "raw_sha256": hashlib.sha256(b"synthetic-racelist-original").hexdigest(),
        "first_write_confirmed": True,
        "readback_confirmed": True,
        "entries": [
            {"lane": lane, "racer_number": 1000 + lane, "active": True}
            for lane in range(1, 7)
        ],
    }
