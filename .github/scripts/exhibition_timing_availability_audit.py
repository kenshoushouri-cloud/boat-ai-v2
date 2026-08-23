# -*- coding: utf-8 -*-
"""Deprecated timing audit.

This script previously inferred exhibition availability time from
v2_realtime_exhibition_snapshots.snapshot_at. That table is mutable: rows are
upserted by (race_id, snapshot_label, lane), and later collection can replace
snapshot_at. Therefore those timestamps cannot prove when data first became
available.

Use bao_exhibition_live_timing_probe.py for contemporaneous official-page
observations. No DB writes or Production changes are performed here.
"""


def main():
    print("EX_TIMING_MODE=deprecated_read_only", flush=True)
    print(
        "EX_TIMING_REASON=mutable_snapshot_at_upsert_cannot_prove_first_availability",
        flush=True,
    )
    print("EX_TIMING_REPLACEMENT=bao_exhibition_live_timing_probe.py", flush=True)
    print("EX_TIMING_POLICY=no_writes_no_production_no_line", flush=True)
    print("EX_TIMING_RESULT=INVALID_SOURCE_DO_NOT_USE", flush=True)


if __name__ == "__main__":
    main()
