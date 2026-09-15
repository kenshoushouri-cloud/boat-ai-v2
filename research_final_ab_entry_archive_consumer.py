# -*- coding: utf-8 -*-
"""Research-only exact equivalence check for final_ab entry snapshots.

The archive rowset is first compared exactly with one online PostgreSQL read.
All analysis inputs are then frozen in memory once. The existing read-only
`analyze_final_ab_features_pg.py` main function is executed twice against those
same frozen results/weather/exhibition/favorite-odds inputs; only entry data is
swapped from the frozen online copy to the verified archive copy. Full stdout
must match exactly. This prevents unrelated live-table changes between two
sequential analysis runs from creating a false archive mismatch.

No Production path imports this module.
"""
from __future__ import annotations

import contextlib
import copy
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


def _entry_map(rows, mod):
    out = defaultdict(dict)
    for r in rows:
        rid = str(r.get("race_id") or "")
        lane = mod.si(r.get("lane"))
        if rid and 1 <= lane <= 6:
            out[rid][lane] = dict(r)
    return dict(out)


def _frozen_loader(value):
    """Return a loader that cannot leak mutations between comparison runs."""
    return lambda: copy.deepcopy(value)


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

    # Freeze every other analysis input exactly once. The previous version ran
    # mod.main() twice against live tables, so unrelated results/odds changes
    # between the two calls could produce a false entry-archive mismatch.
    frozen_results = mod.load_results()
    frozen_weather = mod.load_weather()
    frozen_exhibition = mod.load_exh()
    frozen_online_entry = mod.load_entry()
    frozen_favorite = mod.load_fav()
    frozen_archive_entry = _entry_map(archive_rows, mod)

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
        mod.load_exh = _frozen_loader(frozen_exhibition)
        mod.load_fav = _frozen_loader(frozen_favorite)

        mod.load_entry = _frozen_loader(frozen_online_entry)
        online_stdout = _capture(mod.main)

        mod.load_entry = _frozen_loader(frozen_archive_entry)
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
