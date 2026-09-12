from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "research" / "storage_retention_contract.py"
SPEC = importlib.util.spec_from_file_location("storage_retention_contract", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
ShadowRow = MODULE.ShadowRow
retention_plan = MODULE.retention_plan


def row(key: str, minute: int, *, evaluated: bool = True, window: str = "final") -> ShadowRow:
    return ShadowRow(
        race_id="20260912_01_01",
        ticket="1-2-3",
        run_class="final",
        window_name=window,
        snapshot_key=key,
        snapshot_at=datetime(2026, 9, 12, 1, minute, tzinfo=timezone.utc),
        evaluated=evaluated,
    )


def test_evaluated_group_keeps_latest_only():
    keep, removable = retention_plan([row("a", 0), row("b", 15), row("c", 30)])
    assert [x.snapshot_key for x in keep] == ["c"]
    assert [x.snapshot_key for x in removable] == ["a", "b"]


def test_any_unevaluated_row_blocks_compaction_for_whole_logical_key():
    keep, removable = retention_plan([row("a", 0), row("b", 15, evaluated=False)])
    assert {x.snapshot_key for x in keep} == {"a", "b"}
    assert removable == ()


def test_windows_are_isolated():
    keep, removable = retention_plan([
        row("m1", 0, window="morning"),
        row("m2", 15, window="morning"),
        row("f1", 30, window="final"),
        row("f2", 45, window="final"),
    ])
    assert {x.snapshot_key for x in keep} == {"m2", "f2"}
    assert {x.snapshot_key for x in removable} == {"m1", "f1"}


def test_ambiguous_latest_timestamp_fails_closed():
    with pytest.raises(ValueError, match="ambiguous latest snapshot"):
        retention_plan([row("a", 15), row("b", 15)])


def test_malformed_identity_fails_closed():
    bad = ShadowRow(
        race_id="",
        ticket="1-2-3",
        run_class="final",
        window_name="final",
        snapshot_key="x",
        snapshot_at=datetime(2026, 9, 12, 1, 0, tzinfo=timezone.utc),
        evaluated=True,
    )
    with pytest.raises(ValueError, match="malformed shadow identity"):
        retention_plan([bad])
