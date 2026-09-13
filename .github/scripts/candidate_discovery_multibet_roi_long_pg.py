# -*- coding: utf-8 -*-
"""Long fixed-grid Candidate Discovery multi-bet ROI validation (READ ONLY).

Reuses the exact multi-bet selection/evaluation contract from the 30-day smoke.
The only operational change is bounded parallel retrieval of immutable official K
archives so the longer predeclared historical period can be evaluated without
changing any race, bet-type, point-count, or coverage rule.

No DB writes, no Production change, no LINE, no BUY, no odds/EV gate.
"""
from __future__ import annotations

import importlib.util
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BASE_PATH = HERE / "candidate_discovery_multibet_roi_k_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_multibet_roi_k_pg", BASE_PATH)
base = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(base)

FETCH_WORKERS = max(1, min(4, int(os.getenv("CANDIDATE_MULTIBET_K_FETCH_WORKERS", "4"))))


def fetch_one(ds: str) -> tuple[str, dict[tuple[str, int, str], dict[str, Any]] | None, dict[str, int] | None, str | None]:
    try:
        parsed = base.kmod.parse_multibet_payouts(base.kmod.get_k_text(ds))
        stats = {
            "markers": len(parsed["markers"]),
            "mapped": len(parsed["mapped"]),
            "trifecta": int(parsed["mapped_counts"].get("trifecta", 0)),
            "exacta": int(parsed["mapped_counts"].get("exacta", 0)),
            "trio": int(parsed["mapped_counts"].get("trio", 0)),
        }
        return ds, parsed["by_key"], stats, None
    except Exception as exc:
        return ds, None, None, f"{type(exc).__name__}:{str(exc)[:300]}"


def fetch_official_payouts_parallel(days: list[str]):
    by_day: dict[str, dict[tuple[str, int, str], dict[str, Any]]] = {}
    errors: dict[str, str] = {}
    stats: dict[str, dict[str, int]] = {}
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        for ds, mapping, day_stats, err in pool.map(fetch_one, days):
            if err is not None:
                errors[ds] = err
            else:
                assert mapping is not None and day_stats is not None
                by_day[ds] = mapping
                stats[ds] = day_stats
    return by_day, errors, stats


def main() -> None:
    print("CANDIDATE_MULTIBET_LONG_MODE=fixed_grid_read_only", flush=True)
    print(f"CANDIDATE_MULTIBET_LONG_PERIOD={base.START_DATE}..{base.END_DATE}", flush=True)
    print(f"CANDIDATE_MULTIBET_LONG_K_FETCH_WORKERS={FETCH_WORKERS}", flush=True)
    print("CANDIDATE_MULTIBET_LONG_RULE_CHANGE=0 POSTHOC_TUNING=0", flush=True)
    print("CANDIDATE_MULTIBET_LONG_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)
    base.fetch_official_payouts = fetch_official_payouts_parallel
    base.main()
    # Re-open output only to assert the safety/result contract; do not rewrite it.
    data = json.loads(base.OUTPUT.read_text(encoding="utf-8"))
    if data.get("promotion_allowed") is not False:
        raise RuntimeError("promotion must remain blocked")
    if data.get("purchase_action") is not False or data.get("mutation_performed") is not False:
        raise RuntimeError("unsafe result contract")
    print("CANDIDATE_MULTIBET_LONG_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
