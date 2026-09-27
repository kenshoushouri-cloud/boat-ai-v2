"""Pure prospective F-count diagnostic contract for current V4.

No DB/network/file/LINE/purchase integration. This module validates caller-supplied
pre-result freezes and evaluates caller-supplied finalized winner lanes only.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Mapping, Sequence

JST=timezone(timedelta(hours=9))
SOURCE_CUTOFF=time(8,15)
CORE_RACES=6
F_POSITIVE_THRESHOLD=1
MIN_TOTAL_CORE_RACES=200
MIN_F_POSITIVE_RACES=30
MIN_F_ZERO_RACES=100
MIN_HEAD_ACCURACY_GAP_PT=5.0
REQUIRED_DIRECTIONAL_QUARTERS=3
PURCHASE_ACTION=False


def _aware(value:Any)->datetime:
    dt=value if isinstance(value,datetime) else datetime.fromisoformat(str(value).replace("Z","+00:00"))
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timezone-aware datetime required")
    return dt.astimezone(JST)


def _target_date(value:Any)->date:
    return value if isinstance(value,date) and not isinstance(value,datetime) else date.fromisoformat(str(value))


def validate_freeze(artifact:Mapping[str,Any])->tuple[dict[str,Any],...]:
    if artifact.get("purchase_action") is not False:
        raise ValueError("purchase_action must be false")
    if artifact.get("outcome_read") is not False:
        raise ValueError("freeze must state outcome_read=false")
    target=_target_date(artifact.get("target_date"))
    generated=_aware(artifact.get("generated_at_jst"))
    cutoff=datetime.combine(target,SOURCE_CUTOFF,tzinfo=JST)
    if generated.date()!=target or generated<cutoff:
        raise ValueError("freeze must occur on target date at/after 08:15 JST")
    core=artifact.get("core")
    if not isinstance(core,list) or len(core)!=CORE_RACES:
        raise ValueError("exact six V4 core races required")
    ranks=[]
    seen=set()
    normalized=[]
    for raw in core:
        if not isinstance(raw,Mapping):
            raise ValueError("core row must be mapping")
        race_id=str(raw.get("race_id") or "")
        if not race_id or race_id in seen:
            raise ValueError("unique race_id required")
        seen.add(race_id)
        rank=int(raw.get("daily_rank") or 0)
        ranks.append(rank)
        deadline=_aware(raw.get("deadline_at"))
        if generated>=deadline:
            raise ValueError("freeze must precede every core deadline")
        head=int(raw.get("predicted_head") or 0)
        if head not in range(1,7):
            raise ValueError("predicted_head must be 1..6")
        counts=raw.get("f_counts")
        if not isinstance(counts,Mapping):
            raise ValueError("f_counts mapping required")
        f_counts={}
        for lane in range(1,7):
            value=counts.get(lane,counts.get(str(lane)))
            if type(value) is not int or value<0:
                raise ValueError("six non-negative integer F counts required")
            f_counts[lane]=value
        if any(k in raw for k in ("winner_lane","actual_head","finish_order","payout")):
            raise ValueError("outcome fields forbidden in pre-result freeze")
        normalized.append({
            "race_id":race_id,
            "daily_rank":rank,
            "deadline_at":deadline.isoformat(),
            "predicted_head":head,
            "predicted_head_f_count":f_counts[head],
            "predicted_head_f_positive":f_counts[head]>=F_POSITIVE_THRESHOLD,
            "f_counts":f_counts,
        })
    if sorted(ranks)!=list(range(1,CORE_RACES+1)):
        raise ValueError("daily_rank must be exactly 1..6")
    return tuple(sorted(normalized,key=lambda r:r["daily_rank"]))


def evaluate(freezes:Sequence[Mapping[str,Any]], winners:Mapping[str,int])->dict[str,Any]:
    rows=[]
    for artifact in freezes:
        target=_target_date(artifact.get("target_date")).isoformat()
        for row in validate_freeze(artifact):
            winner=winners.get(row["race_id"])
            if winner is None:
                continue
            if int(winner) not in range(1,7):
                raise ValueError("winner lane must be 1..6")
            rows.append({
                **row,
                "target_date":target,
                "head_correct":row["predicted_head"]==int(winner),
            })

    def agg(items:list[dict[str,Any]])->dict[str,Any]:
        n=len(items)
        return {
            "n":n,
            "head_accuracy_pct":(100.0*sum(1 for x in items if x["head_correct"])/n) if n else None,
        }

    fpos=[r for r in rows if r["predicted_head_f_positive"]]
    fzero=[r for r in rows if not r["predicted_head_f_positive"]]
    rank1=[r for r in rows if r["daily_rank"]==1]
    dates=sorted({r["target_date"] for r in rows})
    qmap={}
    if dates:
        for idx,d in enumerate(dates):
            qmap[d]=min(3,(idx*4)//len(dates))
    quarters=[]
    for q in range(4):
        qi=[r for r in rows if qmap.get(r["target_date"])==q]
        qp=[r for r in qi if r["predicted_head_f_positive"]]
        qz=[r for r in qi if not r["predicted_head_f_positive"]]
        ap=agg(qp); az=agg(qz)
        gap=None
        if ap["n"] and az["n"]:
            gap=float(az["head_accuracy_pct"])-float(ap["head_accuracy_pct"])
        quarters.append({"quarter":q+1,"f_positive":ap,"f_zero":az,"f_zero_minus_f_positive_pt":gap})

    ap=agg(fpos); az=agg(fzero)
    gap=None
    if ap["n"] and az["n"]:
        gap=float(az["head_accuracy_pct"])-float(ap["head_accuracy_pct"])
    directional=sum(1 for q in quarters if q["f_zero_minus_f_positive_pt"] is not None and q["f_zero_minus_f_positive_pt"]>0)
    enough=(
        len(rows)>=MIN_TOTAL_CORE_RACES and
        ap["n"]>=MIN_F_POSITIVE_RACES and
        az["n"]>=MIN_F_ZERO_RACES
    )
    future_hypothesis_supported=bool(
        enough and gap is not None and gap>=MIN_HEAD_ACCURACY_GAP_PT and
        directional>=REQUIRED_DIRECTIONAL_QUARTERS
    )
    return {
        "evaluated_core_races":len(rows),
        "f_positive":ap,
        "f_zero":az,
        "f_zero_minus_f_positive_pt":gap,
        "rank1":agg(rank1),
        "quarters":quarters,
        "directional_quarters":directional,
        "minimum_evidence_met":enough,
        "future_coefficient_preregistration_supported":future_hypothesis_supported,
        "production_promotion_allowed":False,
        "purchase_action":False,
    }
