from pathlib import Path
def test_plan_is_read_only_no_http_no_outcome():
    s=Path("research/v51_beforeinfo_backfill_cost_plan_pg.py").read_text(encoding="utf-8").lower()
    assert "set transaction read only" in s
    assert "requests." not in s
    for t in ("v2_results","v2_odds","insert into","update v2_","delete from"):
        assert t not in s
