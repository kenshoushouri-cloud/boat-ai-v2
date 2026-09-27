from pathlib import Path


def test_manual_checkpoint_workflow_is_manual_only_and_read_only():
    w = Path(
        ".github/workflows/research-v4-provider-selected-forward-checkpoint-manual.yml"
    ).read_text(encoding="utf-8").lower()
    assert "workflow_dispatch:" in w
    assert "schedule:" not in w
    assert "railway run" in w
    assert "".join(("railway", " variable", " list")) not in w
    assert "gh run list" in w
    assert "sha256sum -c" in w
    assert "v4_formal_inventory_manifest" in w
    assert "frozen_provider_inventory" in w


def test_inventory_and_settlement_contracts_remain_fail_closed():
    inventory = Path("research/v4_formal_artifact_inventory.py").read_text(
        encoding="utf-8"
    ).lower()
    settlement = Path("research/v4_formal_artifact_settlement_pg.py").read_text(
        encoding="utf-8"
    ).lower()

    assert "result_read=0 payout_read=0 odds_read=0" in inventory
    assert "db_write=0 line=0 buy=0 prod_change=0 promotion=0" in inventory
    assert "set transaction read only" in settlement
    assert "reconstruct_candidates=0 odds_read=0" in settlement
    assert "db_write=0 line=0 buy=0 prod_change=0 promotion=0" in settlement
    assert "artifact_set_mode=frozen_provider_inventory" not in settlement  # runtime output only
    assert "unavailable" in inventory
