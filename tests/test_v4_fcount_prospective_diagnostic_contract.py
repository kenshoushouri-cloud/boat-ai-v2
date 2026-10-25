from datetime import datetime, timedelta, timezone
import pytest
from research.v4_fcount_prospective_diagnostic_contract import (
    validate_freeze,evaluate,MIN_HEAD_ACCURACY_GAP_PT
)

JST=timezone(timedelta(hours=9))

def freeze(day="2026-10-01", fpos_rank1=False):
    core=[]
    for rank in range(1,7):
        counts={i:0 for i in range(1,7)}
        if fpos_rank1 and rank==1:
            counts[1]=1
        core.append({
            "race_id":f"{day}-R{rank}",
            "daily_rank":rank,
            "deadline_at":f"{day}T10:{rank:02d}:00+09:00",
            "predicted_head":1,
            "f_counts":counts,
        })
    return {
        "target_date":day,
        "generated_at_jst":f"{day}T08:25:00+09:00",
        "outcome_read":False,
        "purchase_action":False,
        "core":core,
    }

def test_validate_exact_six_and_f_counts():
    rows=validate_freeze(freeze(fpos_rank1=True))
    assert len(rows)==6
    assert rows[0]["predicted_head_f_positive"] is True
    assert rows[1]["predicted_head_f_positive"] is False

def test_rejects_outcome_in_freeze():
    x=freeze()
    x["core"][0]["winner_lane"]=1
    with pytest.raises(ValueError):
        validate_freeze(x)

def test_rejects_before_cutoff():
    x=freeze()
    x["generated_at_jst"]="2026-10-01T08:14:59+09:00"
    with pytest.raises(ValueError):
        validate_freeze(x)

def test_evaluator_has_no_promotion_authority():
    x=freeze(fpos_rank1=True)
    winners={row["race_id"]:1 for row in x["core"]}
    out=evaluate([x],winners)
    assert out["production_promotion_allowed"] is False
    assert out["purchase_action"] is False
    assert out["minimum_evidence_met"] is False
    assert MIN_HEAD_ACCURACY_GAP_PT==5.0
