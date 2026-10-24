# -*- coding: utf-8 -*-
"""Research-only exact equivalence check for final_ab exhibition snapshots.

The verified archive rowset is compared exactly with one online PostgreSQL read.
All analysis inputs are then frozen once in memory and the existing read-only
final_ab feature analysis is executed twice; only exhibition is swapped between
the frozen online copy and the verified archive copy. Full stdout equality is
required. No Production path imports this module.
"""
from __future__ import annotations

import contextlib
import copy
from collections import defaultdict
import hashlib
import io
import os

from research_archive_readthrough import EvidenceQuery, JsonlGzipPartitionSource, assert_equivalent


def _capture(fn) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


def _frozen_loader(value):
    return lambda: copy.deepcopy(value)


def _exhibition_map(rows, mod):
    out = defaultdict(dict)
    for r in rows:
        rid = str(r.get("race_id") or "")
        lane = mod.si(r.get("lane"))
        if rid and 1 <= lane <= 6:
            out[rid][lane] = dict(r)
    return dict(out)


def main() -> None:
    manifest_path = os.getenv("FINAL_AB_EXHIBITION_ARCHIVE_MANIFEST", "").strip()
    if not manifest_path:
        raise RuntimeError("FINAL_AB_EXHIBITION_ARCHIVE_MANIFEST is required")
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    import analyze_final_ab_features_pg as mod

    source = JsonlGzipPartitionSource(manifest_path)
    query = EvidenceQuery(
        table="v2_realtime_exhibition_snapshots",
        start_date=mod.START_DATE,
        end_date=mod.END_DATE,
        labels=(mod.SNAPSHOT_LABEL,),
    )
    if not source.covers(query):
        raise RuntimeError("exhibition archive does not exactly cover requested analysis window")

    keep = (
        "race_id",
        "lane",
        "exhibition_time",
        "exhibition_time_rank",
        "start_timing",
        "start_timing_rank",
    )
    archive_rows = [{k: r.get(k) for k in keep} for r in source.fetch(query)]
    online_rows = mod.fetch_all(
        "select race_id,lane,exhibition_time,exhibition_time_rank,start_timing,start_timing_rank "
        "from v2_realtime_exhibition_snapshots where race_date >= %s and race_date <= %s and snapshot_label=%s",
        (mod.START_DATE, mod.END_DATE, mod.SNAPSHOT_LABEL),
    )
    count, row_sha = assert_equivalent(
        archive_rows,
        online_rows,
        key_fields=("race_id", "lane"),
        fields=keep,
    )
    if count <= 0:
        raise AssertionError("exhibition equivalence requires a non-empty partition")

    frozen_results = mod.load_results()
    frozen_weather = mod.load_weather()
    frozen_online_exhibition = mod.load_exh()
    frozen_entry = mod.load_entry()
    frozen_favorite = mod.load_fav()
    frozen_archive_exhibition = _exhibition_map(archive_rows, mod)

    originals = {
        "load_results": mod.load_results,
        "load_weather": mod.load_weather,
        "load_exh": mod.load_exh,
        "load_entry": mod.load_entry,
        "load_fav": mod.load_fav,
    }
    try:
        mod.load_results = _frozen_loader(frozen_results)
        mod.load_weather = _frozen_loader(frozen_weather)
        mod.load_entry = _frozen_loader(frozen_entry)
        mod.load_fav = _frozen_loader(frozen_favorite)

        mod.load_exh = _frozen_loader(frozen_online_exhibition)
        online_stdout = _capture(mod.main)

        mod.load_exh = _frozen_loader(frozen_archive_exhibition)
        archive_stdout = _capture(mod.main)
    finally:
        for name, fn in originals.items():
            setattr(mod, name, fn)

    if online_stdout != archive_stdout:
        online_lines = online_stdout.splitlines()
        archive_lines = archive_stdout.splitlines()
        for i in range(max(len(online_lines), len(archive_lines))):
            a = online_lines[i] if i < len(online_lines) else "<missing>"
            b = archive_lines[i] if i < len(archive_lines) else "<missing>"
            if a != b:
                raise AssertionError(
                    f"final_ab exhibition analysis stdout mismatch line={i + 1} online={a!r} archive={b!r}"
                )
        raise AssertionError("final_ab exhibition analysis stdout mismatch")

    stdout_sha = hashlib.sha256(online_stdout.encode("utf-8")).hexdigest()
    print(
        "FINAL_AB_EXHIBITION_ARCHIVE_COMPARE=PASS "
        f"period={mod.START_DATE}..{mod.END_DATE} label={mod.SNAPSHOT_LABEL} "
        f"rows={count} row_sha256={row_sha} stdout_sha256={stdout_sha}",
        flush=True,
    )
    print("FINAL_AB_EXHIBITION_ARCHIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
