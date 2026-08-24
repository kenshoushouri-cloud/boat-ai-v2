# -*- coding: utf-8 -*-
"""Read-only composition diagnostic for the Forward R05-08 deterioration.

This is descriptive only. It compares fixed groups already identified by the
pre-existing daily stability audit. It must not be used to create date/race-band
filters or tune the Opponent Pressure coefficient.
"""
from __future__ import annotations

import math
import os
from collections import Counter, defaultdict
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row

import opponent_pressure_v24_trifecta_forward as tri
import opponent_pressure_v24_trifecta_head_only_forward as head

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat(os.getenv("OPP_R0508_COMP_START", "2026-08-22"))
END = date.fromisoformat(os.getenv("OPP_R0508_COMP_END", "2026-08-24"))
EPS = 1e-15
UNIT_PRESSURE_COEF = 1.0


def rank_desc(xs: list[float], idx: int) -> int:
    return 1 + sum(1 for j, x in enumerate(xs) if j != idx and x > xs[idx])


def entropy(ps: list[float]) -> float:
    return -sum(p * math.log(max(EPS, p)) for p in ps)


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def hhi(values: list[str]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    n = len(values)
    return sum((c / n) ** 2 for c in counts.values())


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {"n": 0}
    winner_lanes = Counter(int(r["winner_lane"]) for r in rows)
    venues = [str(r["venue"]) for r in rows]
    return {
        "n": n,
        "brier_delta": mean([r["brier_plus"] - r["brier_base"] for r in rows]),
        "logloss_delta": mean([r["ll_plus"] - r["ll_base"] for r in rows]),
        "rank_delta": mean([r["rank_plus"] - r["rank_base"] for r in rows]),
        "winner_delta": mean([r["winner_delta"] for r in rows]),
        "winner_delta_positive": mean([1.0 if r["winner_delta"] > 0 else 0.0 for r in rows]),
        "winner_delta_is_max": mean([1.0 if r["winner_delta_is_max"] else 0.0 for r in rows]),
        "delta_sum": mean([r["delta_sum"] for r in rows]),
        "winner_norm_change": mean([r["winner_norm_change"] for r in rows]),
        "winner_norm_positive": mean([1.0 if r["winner_norm_change"] > 0 else 0.0 for r in rows]),
        "lane_raw_delta": [mean([r["lane_deltas"][i] for r in rows]) for i in range(6)],
        "lane_norm_change": [mean([r["lane_norm_changes"][i] for r in rows]) for i in range(6)],
        "avg_abs_delta": mean([r["avg_abs_delta"] for r in rows]),
        "max_abs_delta": mean([r["max_abs_delta"] for r in rows]),
        "winner_base_p": mean([r["winner_base_p"] for r in rows]),
        "winner_adj_p": mean([r["winner_adj_p"] for r in rows]),
        "winner_first_rank_base": mean([r["winner_first_rank_base"] for r in rows]),
        "winner_first_rank_adj": mean([r["winner_first_rank_adj"] for r in rows]),
        "v24_entropy": mean([r["v24_entropy"] for r in rows]),
        "v24_top_gap": mean([r["v24_top_gap"] for r in rows]),
        "matched_opponents_all": mean([r["matched_opponents_all"] for r in rows]),
        "matched_opponents_winner": mean([r["matched_opponents_winner"] for r in rows]),
        "a1_count": mean([r["a1_count"] for r in rows]),
        "unique_venues": len(set(venues)),
        "venue_hhi": hhi(venues),
        "winner_lanes": winner_lanes,
        "venue_counts": Counter(venues),
    }


def emit(label: str, m: dict[str, Any]) -> None:
    if not m.get("n"):
        print(f"OPP_R0508_COMP={label} n:0", flush=True)
        return
    lane_text = ",".join(f"{k}:{m['winner_lanes'].get(k,0)}" for k in range(1,7))
    venue_text = ",".join(f"{k}:{v}" for k,v in sorted(m["venue_counts"].items()))
    raw_lane = ",".join(f"{i+1}:{m['lane_raw_delta'][i]:+.5f}" for i in range(6))
    norm_lane = ",".join(f"{i+1}:{m['lane_norm_change'][i]:+.5f}" for i in range(6))
    print(
        f"OPP_R0508_COMP={label} n:{m['n']} "
        f"brier_delta:{m['brier_delta']:+.8f} logloss_delta:{m['logloss_delta']:+.8f} rank_delta:{m['rank_delta']:+.3f} "
        f"winner_raw_delta:{m['winner_delta']:+.6f} winner_raw_positive:{m['winner_delta_positive']*100:.1f}% "
        f"winner_raw_is_max:{m['winner_delta_is_max']*100:.1f}% raw_delta_sum:{m['delta_sum']:+.6f} "
        f"winner_norm_change:{m['winner_norm_change']:+.6f} winner_norm_positive:{m['winner_norm_positive']*100:.1f}% "
        f"raw_lane_delta:{raw_lane} norm_lane_change:{norm_lane} "
        f"avg_abs_delta:{m['avg_abs_delta']:.6f} max_abs_delta:{m['max_abs_delta']:.6f} "
        f"winner_first_p:{m['winner_base_p']:.4f}->{m['winner_adj_p']:.4f} "
        f"winner_first_rank:{m['winner_first_rank_base']:.3f}->{m['winner_first_rank_adj']:.3f} "
        f"v24_entropy:{m['v24_entropy']:.4f} v24_top_gap:{m['v24_top_gap']:.4f} "
        f"matched_opponents_all:{m['matched_opponents_all']:.2f} matched_opponents_winner:{m['matched_opponents_winner']:.2f} a1_count:{m['a1_count']:.2f} "
        f"unique_venues:{m['unique_venues']} venue_hhi:{m['venue_hhi']:.4f} winner_lanes:{lane_text} venues:{venue_text}",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("OPP_R0508_COMP_MODE=read_only_fixed_group_composition_no_tuning", flush=True)
    print(f"OPP_R0508_COMP_PERIOD={START}..{END}", flush=True)
    print("OPP_R0508_COMP_GROUPS=2026-08-22_R05_08,2026-08-23_R05_08,2026-08-24_R05_08,2026-08-22_23_R05_08,2026-08-24_R09_12", flush=True)
    print("OPP_R0508_COMP_DELTA_SEMANTICS=adj_win_minus_base_win_is_lane_independent_effect_not_zero_sum_distribution_delta", flush=True)
    print("OPP_R0508_COMP_POLICY=descriptive_only_no_date_filter_no_race_band_filter_no_coefficient_search_no_writes_no_production_no_line", flush=True)

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='120s'")
            cur.execute(
                """
                select s.race_id,s.race_date,s.model_version,s.train_end,s.matched_opponents,s.base_win,s.adj_win,
                       r.first_lane,r.second_lane,r.third_lane,r.result_status,
                       q.venue_id,q.venue_code,q.race_no
                from v2_opponent_pressure_shadow_v2 s
                left join v2_results r on r.race_id=s.race_id
                left join v2_races q on q.race_id=s.race_id
                where s.race_date between %s and %s
                order by s.race_date,s.race_id
                """,
                (START, END),
            )
            shadows = [dict(x) for x in cur.fetchall()]
            ids = [str(x["race_id"]) for x in shadows]
            entries_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
            if ids:
                cur.execute(
                    """
                    select race_id,lane,racer_class,national_win_rate,national_place2_rate,local_place2_rate,avg_st
                    from v2_race_entries where race_id=any(%s) order by race_id,lane
                    """,
                    (ids,),
                )
                for e in cur.fetchall():
                    d=dict(e); entries_by_race[str(d["race_id"])].append(d)

    records: list[dict[str, Any]] = []
    skipped = 0
    for s in shadows:
        lanes=[tri.si(s.get(k),0) for k in ("first_lane","second_lane","third_lane")]
        if str(s.get("result_status") or "") != "official" or any(not 1 <= x <= 6 for x in lanes) or len(set(lanes)) != 3:
            skipped += 1; continue
        if int(s.get("model_version") or 0) != 2 or s.get("train_end") >= s.get("race_date"):
            skipped += 1; continue
        if not isinstance(s.get("base_win"),list) or not isinstance(s.get("adj_win"),list) or len(s["base_win"]) != 6 or len(s["adj_win"]) != 6:
            skipped += 1; continue
        supports=s.get("matched_opponents")
        if not isinstance(supports,list) or len(supports) != 6:
            skipped += 1; continue
        rid=str(s["race_id"]); venue=str(s.get("venue_id") or s.get("venue_code") or "").zfill(2)
        entries=entries_by_race.get(rid,[])
        base=tri.lane_probs(entries,venue)
        if base is None:
            skipped += 1; continue
        delta=[tri.sf(s["adj_win"][i])-tri.sf(s["base_win"][i]) for i in range(6)]
        adj=tri.norm([max(1e-12,min(.999,base[i]+delta[i])) for i in range(6)])
        norm_changes=[adj[i]-base[i] for i in range(6)]
        pb=tri.pl_trifecta(base); ph=head.head_only_trifecta(base,adj)
        ticket=f"{lanes[0]}-{lanes[1]}-{lanes[2]}"; idx=lanes[0]-1
        sorted_base=sorted(base,reverse=True)
        a1=sum(1 for e in entries if tri.si(e.get("racer_class"),0)==4)
        records.append({
            "race_date":str(s["race_date"]),"race_no":tri.si(s.get("race_no"),0),"venue":venue,"winner_lane":lanes[0],
            "brier_base":sum((p-(1.0 if t==ticket else 0.0))**2 for t,p in pb.items()),
            "brier_plus":sum((p-(1.0 if t==ticket else 0.0))**2 for t,p in ph.items()),
            "ll_base":-math.log(max(EPS,pb.get(ticket,0.0))),"ll_plus":-math.log(max(EPS,ph.get(ticket,0.0))),
            "rank_base":float(tri.ticket_rank(pb,ticket)),"rank_plus":float(tri.ticket_rank(ph,ticket)),
            "winner_delta":delta[idx],"winner_delta_is_max":delta[idx] >= max(delta)-1e-15,
            "delta_sum":sum(delta),"winner_norm_change":norm_changes[idx],
            "lane_deltas":delta,"lane_norm_changes":norm_changes,
            "avg_abs_delta":mean([abs(x) for x in delta]),"max_abs_delta":max(abs(x) for x in delta),
            "winner_base_p":base[idx],"winner_adj_p":adj[idx],
            "winner_first_rank_base":float(rank_desc(base,idx)),"winner_first_rank_adj":float(rank_desc(adj,idx)),
            "v24_entropy":entropy(base),"v24_top_gap":sorted_base[0]-sorted_base[1],
            "matched_opponents_all":mean([float(x) for x in supports]),"matched_opponents_winner":float(supports[idx]),"a1_count":float(a1),
        })

    print(f"OPP_R0508_COMP_COVERAGE=shadow:{len(shadows)} evaluated:{len(records)} skipped:{skipped}", flush=True)
    groups: dict[str,list[dict[str,Any]]] = {
        "2026-08-22_R05_08":[r for r in records if r["race_date"]=="2026-08-22" and 5<=r["race_no"]<=8],
        "2026-08-23_R05_08":[r for r in records if r["race_date"]=="2026-08-23" and 5<=r["race_no"]<=8],
        "2026-08-24_R05_08":[r for r in records if r["race_date"]=="2026-08-24" and 5<=r["race_no"]<=8],
        "2026-08-22_23_R05_08":[r for r in records if r["race_date"] in ("2026-08-22","2026-08-23") and 5<=r["race_no"]<=8],
        "2026-08-24_R09_12":[r for r in records if r["race_date"]=="2026-08-24" and 9<=r["race_no"]<=12],
    }
    for label,rr in groups.items(): emit(label,summarize(rr))
    print("OPP_R0508_COMP_INTERPRETATION=COMPOSITION_DIAGNOSTIC_ONLY_NO_POLICY_SELECTION", flush=True)
    print("OPP_R0508_COMP_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_R0508_COMP_RESULT=PASS_READ_ONLY", flush=True)

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        msg=str(exc).replace("\n"," ").replace("\r"," ")[:700]
        print(f"OPP_R0508_COMP_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
