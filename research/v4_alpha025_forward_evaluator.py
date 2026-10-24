# -*- coding: utf-8 -*-
"""Offline evaluator for frozen V4 alpha=0.25 prospective shadow artifacts.

The evaluator never creates tickets. It accepts only:
1) a previously frozen prospective shadow JSON;
2) exact official result rows for the same race_ids.

No model, feature, probability, selector, or ranking code is imported here.
That separation prevents result-after reconstruction.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

FREEZE_JSON = Path(
    os.getenv("V4_ALPHA025_FREEZE_JSON", "v4-alpha025-prospective-shadow.json")
)
RESULT_JSON = Path(
    os.getenv("V4_ALPHA025_RESULT_JSON", "v4-alpha025-official-results.json")
)
OUTPUT_JSON = Path(
    os.getenv("V4_ALPHA025_EVAL_JSON", "v4-alpha025-forward-evaluation.json")
)
EXPECTED_CONTRACT = "v4_alpha025_prospective_shadow_v1"
UNIT_YEN = 100


def norm_ticket(value: Any) -> str | None:
    text = str(value or "").strip().replace(" ", "")
    parts = text.split("-")
    if len(parts) != 3:
        return None
    try:
        lanes = tuple(int(x) for x in parts)
    except Exception:
        return None
    if any(lane < 1 or lane > 6 for lane in lanes) or len(set(lanes)) != 3:
        return None
    return "-".join(str(x) for x in lanes)


def result_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict) and isinstance(payload.get("results"), list):
        rows = payload["results"]
    else:
        raise ValueError("result JSON must be a list or {'results': [...]}")

    out = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("result row must be an object")
        race_id = str(row.get("race_id") or "")
        ticket = norm_ticket(
            row.get("trifecta_ticket")
            or row.get("actual_trifecta")
            or row.get("ticket")
        )
        payout = row.get("trifecta_payout_yen", row.get("payout_yen"))
        try:
            payout_int = int(payout)
        except Exception:
            payout_int = 0
        result_status = str(row.get("result_status") or "official")
        race_status = str(row.get("race_status") or "official")
        if (
            not race_id
            or ticket is None
            or payout_int <= 0
            or result_status != "official"
            or race_status != "official"
        ):
            raise ValueError(f"non-exact official result row: {race_id or '<missing>'}")
        out.append(
            {
                "race_id": race_id,
                "ticket": ticket,
                "payout_yen": payout_int,
            }
        )
    return out


def validate_freeze(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("contract") != EXPECTED_CONTRACT:
        raise ValueError("freeze contract mismatch")
    policy = payload.get("policy") or {}
    if policy.get("alpha") != 0.25:
        raise ValueError("alpha drift")
    for key in (
        "result_read",
        "payout_read",
        "odds_read",
        "db_write",
        "line_sent",
        "purchase_action",
        "promotion_allowed",
        "production_behavior_changed",
    ):
        if policy.get(key) is not False:
            raise ValueError(f"freeze safety flag drift: {key}")
    races = payload.get("races")
    if not isinstance(races, list) or len(races) != 6:
        raise ValueError("freeze must contain exact six races")

    seen: set[str] = set()
    normalized = []
    for row in races:
        if not isinstance(row, dict):
            raise ValueError("freeze race must be an object")
        rid = str(row.get("race_id") or "")
        if not rid or rid in seen:
            raise ValueError("freeze race_id missing/duplicate")
        seen.add(rid)
        control = [norm_ticket(x) for x in row.get("control_top2", [])]
        shadow = [norm_ticket(x) for x in row.get("shadow_top2", [])]
        if (
            len(control) != 2
            or len(shadow) != 2
            or any(x is None for x in control + shadow)
        ):
            raise ValueError(f"frozen exact Top2 required: {rid}")
        normalized.append(
            {
                "race_id": rid,
                "control_top2": control,
                "shadow_top2": shadow,
            }
        )
    return normalized


def evaluate(
    freeze_payload: dict[str, Any],
    result_payload: Any,
) -> dict[str, Any]:
    frozen = validate_freeze(freeze_payload)
    results = {
        row["race_id"]: row
        for row in result_rows(result_payload)
    }
    if set(results) != {row["race_id"] for row in frozen}:
        raise ValueError("result race set must exactly match frozen race set")

    control_hits = shadow_hits = 0
    control_gross = shadow_gross = 0
    control_only = shadow_only = both_hit = both_miss = 0
    rows = []
    for frozen_row in frozen:
        rid = frozen_row["race_id"]
        result = results[rid]
        actual = result["ticket"]
        payout = int(result["payout_yen"])
        control_hit = actual in frozen_row["control_top2"]
        shadow_hit = actual in frozen_row["shadow_top2"]
        control_hits += int(control_hit)
        shadow_hits += int(shadow_hit)
        control_gross += payout if control_hit else 0
        shadow_gross += payout if shadow_hit else 0
        if control_hit and shadow_hit:
            both_hit += 1
        elif control_hit:
            control_only += 1
        elif shadow_hit:
            shadow_only += 1
        else:
            both_miss += 1
        rows.append(
            {
                "race_id": rid,
                "actual_trifecta": actual,
                "payout_yen": payout,
                "control_top2": frozen_row["control_top2"],
                "shadow_top2": frozen_row["shadow_top2"],
                "control_hit": control_hit,
                "shadow_hit": shadow_hit,
            }
        )

    races = len(frozen)
    investment = races * 2 * UNIT_YEN
    return {
        "contract": "v4_alpha025_forward_evaluation_v1",
        "freeze_contract": EXPECTED_CONTRACT,
        "target_date": freeze_payload["freeze"]["target_date"],
        "freeze_at_jst": freeze_payload["freeze"]["freeze_at_jst"],
        "frozen_model_sha256": freeze_payload["model"]["frozen_model_sha256"],
        "races": races,
        "control": {
            "hits": control_hits,
            "hit_rate_percent": round(control_hits / races * 100.0, 3),
            "investment_yen": investment,
            "gross_return_yen": control_gross,
            "roi_percent": round(control_gross / investment * 100.0, 3),
        },
        "shadow": {
            "hits": shadow_hits,
            "hit_rate_percent": round(shadow_hits / races * 100.0, 3),
            "investment_yen": investment,
            "gross_return_yen": shadow_gross,
            "roi_percent": round(shadow_gross / investment * 100.0, 3),
        },
        "paired": {
            "both_hit": both_hit,
            "control_only": control_only,
            "shadow_only": shadow_only,
            "both_miss": both_miss,
            "hit_delta": shadow_hits - control_hits,
            "hit_rate_delta_pp": round(
                (shadow_hits - control_hits) / races * 100.0,
                3,
            ),
        },
        "rows": rows,
        "candidate_reconstruction": False,
        "rerank_performed": False,
        "production_change_allowed": False,
        "purchase_action": False,
    }


def main() -> None:
    freeze_payload = json.loads(FREEZE_JSON.read_text(encoding="utf-8"))
    result_payload = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
    out = evaluate(freeze_payload, result_payload)
    OUTPUT_JSON.write_text(
        json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("V4_ALPHA025_FORWARD_EVAL=" + json.dumps({
        "target_date": out["target_date"],
        "races": out["races"],
        "control_hits": out["control"]["hits"],
        "shadow_hits": out["shadow"]["hits"],
        "hit_delta": out["paired"]["hit_delta"],
    }, sort_keys=True), flush=True)
    print("V4_ALPHA025_CANDIDATE_RECONSTRUCTION=0", flush=True)
    print("V4_ALPHA025_RERANK=0", flush=True)
    print("RESULT=PASS_OFFLINE_FROZEN_EVALUATION", flush=True)


if __name__ == "__main__":
    main()
