from pathlib import Path
import json
import zipfile

from research.v4_formal_day_strength_seed import build_seed


def _write_zip(path: Path, day: str, score: float) -> None:
    payload = {
        "prospective_evidence_eligible": True,
        "purchase_action": False,
        "freeze_provenance": {
            "target_date": day,
            "outcome_read": False,
            "payout_read": False,
        },
        "summary": {"date": day, "core_races": 6, "core_tickets": 12},
        "feed": [
            {"daily_rank": i, "race_score": score, "legacy_carryover": False}
            for i in range(1, 7)
        ],
    }
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("candidate-discovery-v4-prospective-freeze.json", json.dumps(payload))


def test_seed_is_prior_seven_median(tmp_path):
    days = [f"2026-09-{d:02d}" for d in range(21, 28)]
    vals = [0.90, 0.95, 0.91, 0.96, 0.92, 0.94, 0.93]
    for day, value in zip(days, vals):
        _write_zip(tmp_path / f"{day}.zip", day, value)
    result = build_seed(tmp_path)
    assert result["reference_strength"] == 0.93
    assert result["lookback_dates"] == days
    assert result["result_read"] is False
    assert result["db_read"] is False
