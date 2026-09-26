# -*- coding: utf-8 -*-
from pathlib import Path
from research.v4_course_entry_error_contract import contract_metadata
from research.v4_course_entry_error_replay_pg import aggregate, block_for, prediction_metrics


def test_contract_is_diagnostic_only():
    m=contract_metadata()
    assert m["actual_start_course_is_predictor_input"] is False
    assert m["result_and_course_query_after_selection_freeze"] is True
    assert m["threshold_search"] is False
    assert m["coefficient_retune"] is False
    assert m["odds_used"] is False
    assert m["production_change"] is False
    assert m["purchase_action"] is False


def test_block_assignment_matches_canonical_clamp():
    b=[{"block":1,"end":"2026-01-02"},{"block":2,"end":"2026-01-04"}]
    assert block_for("2026-01-01",b)==1
    assert block_for("2026-01-04",b)==2
    assert block_for("2026-01-05",b)==2


def test_prediction_metrics_are_multiclass():
    probs={}
    raw={1:.4,2:.2,3:.15,4:.1,5:.08,6:.07}
    z=sum(raw.values())
    # enough for first marginal: distribute each head uniformly over 20 tail permutations
    for a in range(1,7):
      tails=[(b,c) for b in range(1,7) if b!=a for c in range(1,7) if c not in (a,b)]
      for b,c in tails: probs[f"{a}-{b}-{c}"]=raw[a]/z/20
    m=prediction_metrics(probs,"1-2-3")
    assert m["predicted_head"]==1 and m["head_correct"] is True
    assert m["head_log_loss"]>0 and 0<=m["head_brier"]<=2


def test_aggregate():
    got=aggregate([
      {"head_correct":True,"head_log_loss":.2,"head_brier":.1},
      {"head_correct":False,"head_log_loss":1.2,"head_brier":.8},
    ])
    assert got["head_accuracy_percent"]==50.0
    assert got["head_log_loss"]==0.7
    assert got["head_brier"]==0.45


def test_source_is_read_only_and_outcome_access_after_freeze():
    root=Path(__file__).resolve().parents[1]
    src=(root/"research"/"v4_course_entry_error_replay_pg.py").read_text(encoding="utf-8")
    low=src.lower()
    assert "set transaction read only" in low
    assert src.index("prepared=prepare_day(") < src.index("results=helper.fetch_selected_results(")
    assert src.index("prepared=prepare_day(") < src.index("course_cards=fetch_course_cards(")
    for forbidden in ("insert into","update v2_","delete from","vacuum ","purchase_action=true","v2_odds"):
      assert forbidden not in low
