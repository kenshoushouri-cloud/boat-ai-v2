# -*- coding: utf-8 -*-
"""Pure combiner for manual V4 + S03 Forward checkpoint outputs."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from research.forward_review_gates import s03_m2_gate, v4_formal_gate
from research.v5_candidate_milestone import evaluate_v5_core_progress


def _extract_json_line(text: str, prefix: str) -> dict[str, Any]:
    for line in text.splitlines():
        if line.startswith(prefix):
            value = line[len(prefix):]
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError(f"{prefix} payload must be object")
            return parsed
    raise ValueError(f"missing line: {prefix}")


def build_scorecard(v4: dict[str, Any], s03_text: str, *, end_date: str) -> dict[str, Any]:
    v4_days = int(v4.get("complete_day_count") or 0)
    v4_complete = v4.get("complete_day_only") or {}
    v4_top2 = v4_complete.get("top2") or {}

    s03_coverage = _extract_json_line(s03_text, "S03_M2_COMMON_COVERAGE=")
    s03_overall = _extract_json_line(s03_text, "S03_M2_COMMON_OVERALL=")
    s03_risk = _extract_json_line(s03_text, "S03_M2_COMMON_RISK=")
    s03_halves = _extract_json_line(s03_text, "S03_M2_COMMON_HALVES=")
    s03_bootstrap = _extract_json_line(s03_text, "S03_M2_COMMON_BOOTSTRAP=")

    evaluated = int(s03_overall.get("evaluated") or 0)
    end = date.fromisoformat(end_date)
    v5_core = evaluate_v5_core_progress(
        as_of=end,
        v4_resolved_formal_days=v4_days,
        s03_m2_evaluated=evaluated,
        evidence_contract_clean=True,
    )
    return {
        "contract": "forward_combined_manual_checkpoint_v1",
        "end_date": end_date,
        "v4_formal": {
            "resolved_formal_days": v4_days,
            "complete_day_dates": v4.get("complete_day_dates") or [],
            "top2": v4_top2,
            "robustness": v4.get("robustness") or {},
            "void_races": v4.get("void_races") or [],
            "pending_or_invalid_races": v4.get("pending_or_invalid_races") or [],
            "review_gate": v4_formal_gate(v4_days),
        },
        "s03_m2": {
            "coverage": s03_coverage,
            "overall": s03_overall,
            "risk": s03_risk,
            "chronological_halves": s03_halves,
            "day_bootstrap": s03_bootstrap,
            "review_gate": s03_m2_gate(evaluated),
        },
        "v5_core_milestone": v5_core,
        "safety": {
            "read_only_inputs": True,
            "promotion_allowed": False,
            "production_change": False,
            "line": False,
            "buy": False,
            "purchase_action": False,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v4-json", required=True)
    ap.add_argument("--s03-log", required=True)
    ap.add_argument("--end-date", required=True)
    ap.add_argument("--output", default="forward-combined-checkpoint.json")
    args = ap.parse_args()

    v4 = json.loads(Path(args.v4_json).read_text(encoding="utf-8"))
    s03_text = Path(args.s03_log).read_text(encoding="utf-8")
    out = build_scorecard(v4, s03_text, end_date=args.end_date)
    Path(args.output).write_text(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("FORWARD_COMBINED_V4_GATE=" + json.dumps(out["v4_formal"]["review_gate"], sort_keys=True))
    print("FORWARD_COMBINED_S03_GATE=" + json.dumps(out["s03_m2"]["review_gate"], sort_keys=True))
    print("FORWARD_COMBINED_V5_CORE=" + json.dumps(out["v5_core_milestone"], sort_keys=True))
    print("FORWARD_COMBINED_RESULT=PASS_PURE_COMBINE")


if __name__ == "__main__":
    main()
