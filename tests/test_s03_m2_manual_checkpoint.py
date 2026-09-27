from pathlib import Path


def test_s03_manual_workflow_is_manual_only_and_read_only():
    w = Path(
        ".github/workflows/research-s03-m2-forward-checkpoint-manual.yml"
    ).read_text(encoding="utf-8").lower()
    assert "workflow_dispatch:" in w
    assert "schedule:" not in w
    assert "railway run" in w
    assert "".join(("railway", " variable", " list")) not in w
    assert "s03_forward_end" in w


def test_s03_checkpoint_script_is_parameterized_but_frozen_rule():
    t = Path("research/s03_m2_common_economics_pg.py").read_text(
        encoding="utf-8"
    ).lower()
    assert 'os.getenv("s03_forward_start", "2026-09-13")' in t
    assert 'os.getenv("s03_forward_end", "2026-09-27")' in t
    assert "set transaction read only" in t
    assert "score > 0.0" in t
    assert "s03_m2_common_remaining_to_100" in t
    assert "pass_read_only_checkpoint" in t
