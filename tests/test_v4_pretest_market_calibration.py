# -*- coding: utf-8 -*-
from research.v4_pretest_market_calibration_pg import (
    CALIB_END,
    CALIB_START,
    HOLD_END,
    HOLD_START,
)
from research.v4_market_residual_value_walkforward_pg import BETA_GRID


def test_pretest_is_strictly_before_heldout():
    assert CALIB_START.isoformat() == "2026-07-01"
    assert CALIB_END.isoformat() == "2026-08-24"
    assert HOLD_START.isoformat() == "2026-08-25"
    assert HOLD_END.isoformat() == "2026-09-22"
    assert CALIB_END < HOLD_START


def test_beta_grid_is_frozen_existing_grid():
    assert BETA_GRID == (0.0, 0.10, 0.25, 0.50, 1.0)


def test_source_freezes_all_betas_before_result_and_is_read_only():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = (
        root / "research/v4_pretest_market_calibration_pg.py"
    ).read_text(encoding="utf-8")
    assert source.index("frozen = {") < source.index(
        "results = hist.fetch_selected_results"
    )
    assert source.index("selected_beta, calibration = mr.choose_beta(calibration_rows)") > source.index(
        "conn.rollback()"
    )
    low = source.lower()
    assert "set transaction read only" in low
    assert "heldout_profit_used_for_beta_selection" in low
    for forbidden in (
        "insert into",
        "update v2_",
        "delete from",
        "vacuum ",
        "purchase_action=true",
    ):
        assert forbidden not in low


def test_workflow_is_non_enumerating():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/v4-pretest-market-calibration.yml"
    ).read_text(encoding="utf-8").lower()
    assert "railway run" in workflow
    assert "postgres-recovery" in workflow
    assert "".join(("railway", " variable", " list")) not in workflow
    assert "".join(("print", "env")) not in workflow
