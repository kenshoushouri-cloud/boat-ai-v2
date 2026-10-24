# -*- coding: utf-8 -*-
"""Research-only exact equivalence check for final_ab weather snapshots.

The verified archive rowset is compared exactly with one online PostgreSQL read.
All analysis inputs are then frozen once in memory and the existing read-only
final_ab feature analysis is executed twice; only weather is swapped between
the frozen online copy and the verified archive copy. Full stdout equality is
required. No Production path imports this module.
"""
from __future__ import annotations

import contextlib
import copy
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


def main() -> None:
    manifest_path = os.getenv("FINAL_AB_WEATHER_ARCHIVE_MANIFEST", "").strip()
    if not manifest_path:
        raise RuntimeError("FINAL_AB_WEATHER_ARCHIVE_MANIFEST is required")
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required")

    import analyze_final_ab_features_pg as mod

    source = JsonlGzipPartitionSource(manifest_path)
    query = EvidenceQuery(
        table="v2_realtime_weather_snapshots",
        start_date=mod.START_DATE,
        end_date=mod.END_DATE,
        labels=(mod.SNAPSHOT_LABEL,),
    )
    if not source.covers(query):
        raise RuntimeError("weather archive does not exactly cover requested analysis window")

    keep = (
        "race_id",
        "weather",
        "temperature_c",
        "water_temperature_c",
        "wind_speed_m",
        "wind_direction",
        "wave_height_cm",
    )
    archive_rows = [{k: r.get(k) for k in keep} for r in source.fetch(query)]
    online_rows = mod.fetch_all(
        "select race_id,weather,temperature_c,water_temperature_c,wind_speed_m,wind_direction,wave_height_cm "
        "from v2_realtime_weather_snapshots where race_date >= %s and race_date <= %s and snapshot_label=%s",
        (mod.START_DATE, mod.END_DATE, mod.SNAPSHOT_LABEL),
    )
    count, row_sha = assert_equivalent(
        archive_rows,
        online_rows,
        key_fields=("race_id",),
        fields=keep,
    )
    if count <= 0:
        raise AssertionError("weather equivalence requires a non-empty partition")

    frozen_results = mod.load_results()
    frozen_online_weather = mod.load_weather()
    frozen_exhibition = mod.load_exh()
    frozen_entry = mod.load_entry()
    frozen_favorite = mod.load_fav()
    frozen_archive_weather = {
        str(r["race_id"]): dict(r) for r in archive_rows if r.get("race_id")
    }

    originals = {
        "load_results": mod.load_results,
        "load_weather": mod.load_weather,
        "load_exh": mod.load_exh,
        "load_entry": mod.load_entry,
        "load_fav": mod.load_fav,
    }
    try:
        mod.load_results = _frozen_loader(frozen_results)
        mod.load_exh = _frozen_loader(frozen_exhibition)
        mod.load_entry = _frozen_loader(frozen_entry)
        mod.load_fav = _frozen_loader(frozen_favorite)

        mod.load_weather = _frozen_loader(frozen_online_weather)
        online_stdout = _capture(mod.main)

        mod.load_weather = _frozen_loader(frozen_archive_weather)
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
                    f"final_ab weather analysis stdout mismatch line={i + 1} online={a!r} archive={b!r}"
                )
        raise AssertionError("final_ab weather analysis stdout mismatch")

    stdout_sha = hashlib.sha256(online_stdout.encode("utf-8")).hexdigest()
    print(
        "FINAL_AB_WEATHER_ARCHIVE_COMPARE=PASS "
        f"period={mod.START_DATE}..{mod.END_DATE} label={mod.SNAPSHOT_LABEL} "
        f"rows={count} row_sha256={row_sha} stdout_sha256={stdout_sha}",
        flush=True,
    )
    print("FINAL_AB_WEATHER_ARCHIVE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
