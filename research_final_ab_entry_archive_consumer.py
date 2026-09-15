# -*- coding: utf-8 -*-
"""Research-only exact equivalence check for final_ab entry snapshots.

Runs the existing read-only final_ab feature analysis unchanged against online
PostgreSQL entry rows, then runs it again with only `load_entry()` replaced by
a verified archive partition. Both the entry rowset digest and the full analysis
stdout must match exactly. No Production path imports this module.
"""
from __future__ import annotations

import contextlib
from collections import defaultdict
import hashlib
import io
import os

from research_archive_readthrough import (
    EvidenceQuery,
    JsonlGzipPartitionSource,
    assert_equivalent,
)


def _capture(fn) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


def main() -> None:
    manifest_path = os.getenv("FINAL_AB_ENTRY_ARCHIVE_MANIFEST", "").strip()
    if not manifest_path:
        raise RuntimeError("FINAL_AB_ENTRY_ARCHIVE_MANIFEST is required")
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    import analyze_final_ab_features_pg as mod

    source = JsonlGzipPartitionSource(manifest_path)
    query = EvidenceQuery(
        table="v2_realtime_entry_snapshots",
        start_date=mod.START_DATE,
        end_date=mod.END_DATE,
        labels=(mod.SNAPSHOT_LABEL,),
    )
    if not source.covers(query):
        raise RuntimeError("entry archive does not exactly cover requested analysis window")

    archive_all = [dict(r) for r in source.fetch(query)]
    keep = ("race_id", "lane", "is_course_changed")
    archive_rows = [{k: r.get(k) for k in keep} for r in archive_all]
    online_rows = mod.fetch_all(
        "select race_id,lane,is_course_changed from v2_realtime_entry_snapshots "
        "where race_date >= %s and race_date <= %s and snapshot_label=%s",
        (mod.START_DATE, mod.END_DATE, mod.SNAPSHOT_LABEL),
    )
    count, row_sha = assert_equivalent(
        archive_rows,
        online_rows,
        key_fields=("race_id", "lane"),
        fields=keep,
    )

    def archive_load_entry():
        out = defaultdict(dict)
        for r in archive_rows:
            rid = str(r.get("race_id") or "")
            lane = mod.si(r.get("lane"))
            if rid and 1 <= lane <= 6:
                out[rid][lane] = r
        return dict(out)

    online_stdout = _capture(mod.main)
    original_load_entry = mod.load_entry
    mod.load_entry = archive_load_entry
    try:
        archive_stdout = _capture(mod.main)
    finally:
        mod.load_entry = original_load_entry

    if online_stdout != archive_stdout:
        online_lines = online_stdout.splitlines()
        archive_lines = archive_stdout.splitlines()
        for i in range(max(len(online_lines), len(archive_lines))):
            a = online_lines[i] if i < len(online_lines) else "<missing>"
            b = archive_lines[i] if i < len(archive_lines) else "<missing>"
            if a != b:
                raise AssertionError(
                    f"final_ab analysis stdout mismatch line={i + 1} online={a!r} archive={b!r}"
                )
        raise AssertionError("final_ab analysis stdout mismatch")

    stdout_sha = hashlib.sha256(online_stdout.encode("utf-8")).hexdigest()
    print(
        "FINAL_AB_ENTRY_ARCHIVE_COMPARE=PASS "
        f"period={mod.START_DATE}..{mod.END_DATE} label={mod.SNAPSHOT_LABEL} "
        f"rows={count} row_sha256={row_sha} stdout_sha256={stdout_sha}",
        flush=True,
    )
    print("FINAL_AB_ENTRY_ARCHIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
