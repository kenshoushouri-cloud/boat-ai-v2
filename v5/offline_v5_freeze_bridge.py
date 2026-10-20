# -*- coding: utf-8 -*-
"""Pure V5 fixed-core math -> candidate paper-shadow freeze (no HTTP/DB/BUY).

This does not load live features, prove acquisition provenance, freeze an
independent first observation, send alerts, settle races, or verify real ROI.
Only separately supplied source evidence is considered. All authority flags
remain FALSE even if a candidate can be locally journaled for research.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from v5.forward_shadow_freeze import prepare_candidate
from v5.offline_mainline_inference import (
    FROZEN_TEMPERATURE, FROZEN_WEIGHTS,
    OfflineV5InferenceInput, check_offline_v5_inference,
)
from v5.offline_trifecta_shadow_ranking import rank_offline_v5_trifectas

MODEL_VERSION = "v5-strong-core-fixed-v1"


def _digest(data: object) -> str:
    data_bytes = json.dumps(data, ensure_ascii=False, sort_keys=True,
                            allow_nan=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data_bytes).hexdigest()


def build_paper_shadow_freeze(
    case: OfflineV5InferenceInput, *,
    deadline_at: str,
    exhibition: dict,
    odds: dict,
    ticket_count: int,
    stake_per_ticket_yen: int,
    now: datetime | None = None,
) -> dict:
    """Compute true V5 fixed-core *math* and freeze prospective mock tickets.

    The caller must independently prove where each factor and source snapshot
    originated. No caller-controlled synthetic fixture can be promoted to
    authenticated real-world Forward/BUY eligibility by this function.
    """
    current = datetime.now(timezone.utc) if now is None else now
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("clock must be timezone aware")
    current = current.astimezone(timezone.utc)
    if type(case) is not OfflineV5InferenceInput:
        raise ValueError("V5 inference input required")
    cutoff = case.decision_cutoff_at
    if not isinstance(cutoff, datetime) or cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("invalid V5 decision cutoff")
    seconds_since_cutoff = (current - cutoff.astimezone(timezone.utc)).total_seconds()
    if not 0 <= seconds_since_cutoff <= 60:
        raise ValueError("stale or future V5 scoring cutoff")
    verdict = check_offline_v5_inference(case)
    if not verdict.synthetic_math_consistent:
        raise ValueError("V5 six-lane inference hard hold: " + verdict.reason)
    ranked = rank_offline_v5_trifectas(verdict, ticket_count=ticket_count)
    if (not ranked.synthetic_math_consistent
            or len(ranked.ticket_distribution) != 120
            or len(ranked.top_tickets) != ticket_count
            or any(getattr(ranked, x) is not False for x in
                   ("original_first_observation_verified", "forward_eligible",
                    "buy_eligible"))):
        raise ValueError("V5 3-ren-tan ranking hard hold: " + ranked.reason)

    input_digest = _digest({
        "race_id": case.race_id,
        "decision_cutoff_at": cutoff.isoformat(),
        "lane_racer_numbers": case.lane_racer_numbers,
        "base_probabilities": case.base_probabilities,
        "factors": {k: case.factors[k] for k, _ in FROZEN_WEIGHTS},
        "frozen_weights": FROZEN_WEIGHTS,
        "frozen_temperature": FROZEN_TEMPERATURE,
    })
    manifest = {
        "race_id": case.race_id,
        "deadline_at": deadline_at,
        "model_family": "V5",
        "model_version": MODEL_VERSION,
        "exhibition": exhibition,
        "odds": odds,
        "selected_tickets": [ticket for ticket, _ in ranked.top_tickets],
        "stake_per_ticket_yen": stake_per_ticket_yen,
        "synthetic_v5_inference_input_sha256": input_digest,
        "synthetic_ranking_sha256": _digest(ranked.ticket_distribution),
    }
    record = prepare_candidate(manifest, now=current)
    record["synthetic_v5_math_only"] = True
    record["source_provenance"] = "UNVERIFIED_FIRST_OBSERVATION"
    record["original_first_observation_verified"] = False
    record["forward_eligible"] = False
    record["buy_eligible"] = False
    return record
