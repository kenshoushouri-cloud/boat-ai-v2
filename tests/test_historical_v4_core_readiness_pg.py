# -*- coding: utf-8 -*-
import json
from pathlib import Path

import pytest

from research.historical_v4_core_readiness_pg import load_overlay


def _payload():
    return {
        "contract": "HISTORICAL_OPPONENT_EPHEMERAL_RECONSTRUCT_V1",
        "target_outcome_read": False,
        "database_write": False,
        "existing_rows_changed": False,
        "production_change": False,
        "rows": [
            {
                "race_id": "20260901_01_01",
                "race_date": "2026-09-01",
                "train_end": "2026-08-31",
                "matched_opponents": [4, 4, 4, 4, 4, 4],
                "base_win": [0.1] * 6,
                "adj_win": [0.1] * 6,
                "provenance": "ephemeral_historical102_strict_prior_only",
            }
        ],
    }


def test_load_overlay_accepts_frozen_strict_prior_artifact(tmp_path):
    p = tmp_path / "opp.json"
    p.write_text(json.dumps(_payload()), encoding="utf-8")
    out = load_overlay(str(p))
    assert set(out) == {"20260901_01_01"}


def test_load_overlay_rejects_outcome_read(tmp_path):
    x = _payload()
    x["target_outcome_read"] = True
    p = tmp_path / "opp.json"
    p.write_text(json.dumps(x), encoding="utf-8")
    with pytest.raises(ValueError):
        load_overlay(str(p))


def test_core_readiness_source_is_result_blind_and_read_only():
    source = Path("research/historical_v4_core_readiness_pg.py").read_text(
        encoding="utf-8"
    ).lower()
    assert "set transaction read only" in source
    assert "opponent_overlay" in source
    for token in (
        "v2_results",
        "v2_result_entries",
        "v2_odds",
        "payout_yen",
        "insert into",
        "update v2_",
        "delete from",
    ):
        assert token not in source
