# -*- coding: utf-8 -*-
"""Research-only archive equivalence harness for probability calibration.

Runs the existing read-only `backtest_prob_calibration_pg.py` twice over one
exact archive partition: first with its normal PostgreSQL odds reads, then with
only `v2_odds_trifecta` reads intercepted by a verified archive source.  The
original consumer is not modified and all non-odds evidence remains read-only
in PostgreSQL.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import os
import re
from datetime import date, timedelta
from typing import Any

from research_archive_readthrough import EvidenceQuery, JsonlGzipPartitionSource


def _capture(fn) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


def _parse_date(name: str) -> date:
    raw = os.getenv(name, "").strip()
    if not raw:
        raise RuntimeError(f"{name} is required")
    return date.fromisoformat(raw)


def main() -> None:
    manifest_path = os.getenv("PROB_CAL_BASE_ODDS_ARCHIVE_MANIFEST", "").strip()
    if not manifest_path:
        raise RuntimeError("PROB_CAL_BASE_ODDS_ARCHIVE_MANIFEST is required")
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    start = _parse_date("BACKTEST_START_DATE")
    end = _parse_date("BACKTEST_END_DATE")
    if start > end:
        raise RuntimeError("BACKTEST_START_DATE must be <= BACKTEST_END_DATE")

    source = JsonlGzipPartitionSource(manifest_path)
    query = EvidenceQuery(
        table="v2_odds_trifecta",
        start_date=start.isoformat(),
        end_date=end.isoformat(),
    )
    if not source.covers(query):
        raise RuntimeError("archive manifest does not exactly cover calibration period")
    archive_rows = [dict(r) for r in source.fetch(query)]

    mod = importlib.import_module("backtest_prob_calibration_pg")
    original_fetch_all = mod.fetch_all

    p = start.strftime("%Y%m%d")
    np = (end + timedelta(days=1)).strftime("%Y%m%d")
    count_rows = original_fetch_all(
        "select count(*)::bigint as n from v2_odds_trifecta where race_id >= %s and race_id < %s",
        (p, np),
    )
    online_count = int((count_rows[0] if count_rows else {}).get("n") or 0)
    if online_count != len(archive_rows):
        raise AssertionError(
            f"online/archive odds row-count mismatch online={online_count} archive={len(archive_rows)}"
        )

    online_output = _capture(mod.main)

    def archive_fetch_all(sql: str, params: Any = ()):
        normalized = " ".join(str(sql).lower().split())
        if "from v2_odds_trifecta" not in normalized:
            return original_fetch_all(sql, params)
        if not isinstance(params, (tuple, list)) or len(params) != 2:
            raise RuntimeError(f"unexpected odds query params: {params!r}")
        lo, hi = str(params[0]), str(params[1])
        rows = [
            {
                "race_id": r.get("race_id"),
                "ticket": r.get("ticket"),
                "odds": r.get("odds"),
            }
            for r in archive_rows
            if lo <= str(r.get("race_id") or "") < hi
        ]
        rows.sort(key=lambda r: (str(r.get("race_id") or ""), str(r.get("ticket") or "")))
        return rows

    mod.fetch_all = archive_fetch_all
    try:
        archive_output = _capture(mod.main)
    finally:
        mod.fetch_all = original_fetch_all

    if online_output != archive_output:
        online_lines = online_output.splitlines()
        archive_lines = archive_output.splitlines()
        first_diff = None
        for i in range(max(len(online_lines), len(archive_lines))):
            a = online_lines[i] if i < len(online_lines) else "<missing>"
            b = archive_lines[i] if i < len(archive_lines) else "<missing>"
            if a != b:
                first_diff = (i + 1, a, b)
                break
        raise AssertionError(f"probability calibration stdout mismatch first_diff={first_diff!r}")

    ready = re.search(r"^ready_races=(\d+)$", online_output, re.MULTILINE)
    tickets = re.search(r"^ticket_rows=(\d+)$", online_output, re.MULTILINE)
    n02 = re.search(r"^N02_ALL: bets=(\d+)", online_output, re.MULTILINE)
    print(
        "PROB_CAL_ARCHIVE_COMPARE=PASS "
        f"period={start.isoformat()}..{end.isoformat()} "
        f"online_odds_rows={online_count} archive_odds_rows={len(archive_rows)} "
        f"ready_races={ready.group(1) if ready else 'unknown'} "
        f"ticket_rows={tickets.group(1) if tickets else 'unknown'} "
        f"n02_bets={n02.group(1) if n02 else 'unknown'}",
        flush=True,
    )
    print("PROB_CAL_ARCHIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
