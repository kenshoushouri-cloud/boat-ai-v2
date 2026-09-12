from datetime import datetime, timezone
from pathlib import Path

import pytest

import v25_final_realtime_pipeline_pg as final_pipeline


def _t(hour: int, minute: int) -> datetime:
    return datetime(2026, 9, 12, hour, minute, tzinfo=timezone.utc)


def test_timestamped_mode_preserves_existing_key_shape_and_uniqueness():
    first = final_pipeline._motor2_final_snapshot_key(
        "2026-09-12", _t(8, 0), "timestamped"
    )
    second = final_pipeline._motor2_final_snapshot_key(
        "2026-09-12", _t(8, 15), "timestamped"
    )
    assert first == "20260912_final_080000"
    assert second == "20260912_final_081500"
    assert first != second


def test_latest_per_race_mode_is_stable_across_repeated_final_runs():
    first = final_pipeline._motor2_final_snapshot_key(
        "2026-09-12", _t(8, 0), "latest_per_race"
    )
    second = final_pipeline._motor2_final_snapshot_key(
        "2026-09-12", _t(8, 15), "latest_per_race"
    )
    assert first == second == "20260912_final_latest"


def test_unknown_mode_fails_closed():
    with pytest.raises(RuntimeError):
        final_pipeline._motor2_final_snapshot_key(
            "2026-09-12", _t(8, 0), "unknown"
        )


def test_runtime_default_is_timestamped_and_no_activation_is_baked_in():
    source = Path("v25_final_realtime_pipeline_pg.py").read_text(encoding="utf-8")
    assert 'os.getenv("MOTOR2_FINAL_SNAPSHOT_MODE", "timestamped")' in source
    assert '"latest_per_race"' in source
    assert "setdefault(\"MOTOR2_FINAL_SNAPSHOT_MODE\"" not in source
    assert "MOTOR2_FINAL_SNAPSHOT_MODE=latest_per_race" not in source
