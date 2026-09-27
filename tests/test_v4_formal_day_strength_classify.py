import json
import zipfile
from pathlib import Path

from research.v4_formal_day_strength_classify import classify


def write_zip(path: Path, day: str, score: float) -> None:
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


def test_classifies_future_target_from_prior_files_only(tmp_path):
    prior_dir = tmp_path / "prior"
    prior_dir.mkdir()
    vals = [0.90, 0.91, 0.92, 0.93, 0.94, 0.95, 0.96]
    for d, v in zip(range(21, 28), vals):
        write_zip(prior_dir / f"2026-09-{d:02d}.zip", f"2026-09-{d:02d}", v)

    target = tmp_path / "2026-09-28.zip"
    write_zip(target, "2026-09-28", 0.935)
    result = classify(target, prior_dir)

    assert result["reference_strength"] == 0.93
    assert result["classification"] == "KEEP_SHADOW"
    assert result["formal_action_changed"] is False
    assert result["promotion_allowed"] is False
