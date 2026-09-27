# -*- coding: utf-8 -*-
"""Pure compatibility proof between the current formal V4 artifact and #400 adapter.

Caller supplies the already-frozen formal JSON. F counts are synthetic sentinels
only; this script never reads a DB/network/result/payout/odds source.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research.candidate_discovery_v4_capture_arbiter import canonical_core_payload_sha256
from research.v4_fcount_companion_adapter import build_companion_from_entry_rows

EXPECTED_FORMAL_CORE_SHA256 = "8907e2443a172d7938395145824497479f3f3bf23d3170943973545adc47f8d3"
CAPTURED_AT_JST = "2026-09-27T08:29:45+09:00"


def synthetic_rows(formal: dict[str, Any]) -> list[dict[str, Any]]:
    core = sorted(
        [
            r for r in formal.get("feed", [])
            if r.get("daily_rank") is not None and r.get("legacy_carryover") is False
        ],
        key=lambda r: int(r["daily_rank"]),
    )
    if len(core) != 6:
        raise ValueError("exact six formal rows required")
    rows = []
    for race_index, row in enumerate(core):
        rid = str(row["race_id"])
        for lane in range(1, 7):
            rows.append({
                "race_id": rid,
                "lane": lane,
                # deterministic synthetic sentinel, never evidence
                "f_count": (race_index + lane) % 3,
            })
    return rows


def verify(formal: dict[str, Any]) -> dict[str, Any]:
    before = canonical_core_payload_sha256(formal)
    if before != EXPECTED_FORMAL_CORE_SHA256:
        raise ValueError(f"unexpected formal core hash: {before}")

    companion, companion_sha = build_companion_from_entry_rows(
        formal,
        synthetic_rows(formal),
        captured_at_jst=CAPTURED_AT_JST,
    )
    after = canonical_core_payload_sha256(formal)
    if before != after:
        raise RuntimeError("formal artifact changed")
    if companion["formal_v4_canonical_core_sha256"] != before:
        raise RuntimeError("companion not bound to formal core")
    if companion["outcome_read"] is not False:
        raise RuntimeError("outcome_read must remain false")
    if companion["odds_read"] is not False or companion["payout_read"] is not False:
        raise RuntimeError("odds/payout read must remain false")
    if companion["purchase_action"] is not False:
        raise RuntimeError("purchase_action must remain false")
    return {
        "formal_core_sha256": before,
        "companion_sha256": companion_sha,
        "core_rows": len(companion["core"]),
        "synthetic_entry_rows": 36,
        "synthetic_only": True,
        "db_read": False,
        "result_read": False,
        "odds_read": False,
        "payout_read": False,
        "db_write": False,
        "persistence": False,
        "production_change": False,
        "purchase_action": False,
    }


def main(path: str) -> None:
    formal = json.loads(Path(path).read_text(encoding="utf-8"))
    print("FCOUNT_COMPAT_SYNTHETIC_ONLY=1")
    print("FCOUNT_COMPAT_DB_READ=0 RESULT_READ=0 ODDS_READ=0 PAYOUT_READ=0")
    print("FCOUNT_COMPAT_DB_WRITE=0 PERSISTENCE=0 PROD_CHANGE=0 BUY=0")
    print("FCOUNT_COMPAT_RESULT_JSON=" + json.dumps(verify(formal), sort_keys=True))
    print("FCOUNT_COMPAT_RESULT=PASS_PURE_CURRENT_ARTIFACT")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: v4_fcount_current_artifact_compat.py FORMAL.json")
    main(sys.argv[1])
