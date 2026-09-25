# -*- coding: utf-8 -*-
"""Read-only archive-equivalence harness for compare_motor_boat_ab_pg.py.

The historical analysis module itself is left unchanged. This harness runs it
once against the still-online base-odds table and once with only its
v2_odds_trifecta fetch intercepted by a verified archive partition. Exact
stdout equality is required. All other evidence remains PostgreSQL read-only.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import os
import re
from typing import Any

import compare_motor_boat_ab_pg as target
from research_archive_readthrough import EvidenceQuery, JsonlGzipPartitionSource


def _capture() -> str:
    buf = StringIO()
    with redirect_stdout(buf):
        target.main()
    return buf.getvalue().replace("\r\n", "\n")


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")
    manifest = os.getenv("MOTOR_BOAT_BASE_ODDS_ARCHIVE_MANIFEST", "").strip()
    if not manifest:
        raise RuntimeError("MOTOR_BOAT_BASE_ODDS_ARCHIVE_MANIFEST is required")

    source = JsonlGzipPartitionSource(manifest)
    query = EvidenceQuery(
        table="v2_odds_trifecta",
        start_date=target.START,
        end_date=target.END,
    )
    archive_rows = [dict(r) for r in source.fetch(query)]

    original_fetch = target.fetch_all
    online_output = _capture()

    odds_query_calls = 0

    def archive_fetch(sql: str, params: Any = None):
        nonlocal odds_query_calls
        normalized = re.sub(r"\s+", " ", str(sql).strip().lower())
        if "from v2_odds_trifecta" in normalized:
            odds_query_calls += 1
            return archive_rows
        return original_fetch(sql, params)

    target.fetch_all = archive_fetch
    try:
        archive_output = _capture()
    finally:
        target.fetch_all = original_fetch

    if odds_query_calls != 1:
        raise RuntimeError(f"unexpected archive odds query calls: {odds_query_calls}")
    if online_output != archive_output:
        online_lines = online_output.splitlines()
        archive_lines = archive_output.splitlines()
        first = None
        for idx, (a, b) in enumerate(zip(online_lines, archive_lines), 1):
            if a != b:
                first = (idx, a, b)
                break
        if first is None and len(online_lines) != len(archive_lines):
            first = (min(len(online_lines), len(archive_lines)) + 1, "<length mismatch>", "<length mismatch>")
        raise AssertionError(f"motor/boat analysis online/archive output mismatch first={first}")

    analyzed = "unknown"
    for line in online_output.splitlines():
        if line.startswith("analyzed_races="):
            analyzed = line.split("=", 1)[1].strip()
            break

    print(
        f"MOTOR_BOAT_ARCHIVE_COMPARE=PASS period={target.START}..{target.END} "
        f"archive_odds_rows={len(archive_rows)} analyzed_races={analyzed}",
        flush=True,
    )
    print("MOTOR_BOAT_ARCHIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
