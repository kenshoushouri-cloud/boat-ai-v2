# -*- coding: utf-8 -*-
"""
compare_exhibition_brank_roi_pg.py

現行Bランク基準と、展示タイム補正を加えたBランク基準を比較します。

比較:
- BASELINE: 展示補正なし
- BALANCED: 展示タイム順位 weight=0.20、展示ST=0、強風補正=0

対象条件:
- prob_rank 11～20
- market_rank 1
- odds 3.0～5.0未満
- 1～9R

読み取り専用。LINE送信・DB更新なし。

Railway Start Command:
    python -u compare_exhibition_brank_roi_pg.py

必要Variables:
    DATABASE_URL

任意Variables:
    ANALYZE_START_DATE=2026-07-05
    ANALYZE_END_DATE=2026-07-14
    SNAPSHOT_LABEL=final_ab
    BRANK_SAMPLE_LIMIT=50
"""

from __future__ import annotations
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from db_pg import fetch_all

JST = timezone(timedelta(hours=9))
START = os.getenv("ANALYZE_START_DATE", "2026-07-05")
END = os.getenv("ANALYZE_END_DATE") or datetime.now(JST).strftime("%Y-%m-%d")
LABEL = os.getenv("SNAPSHOT_LABEL", "final_ab")
SAMPLE_LIMIT = max(1, int(os.getenv("BRANK_SAMPLE_LIMIT", "50")))

TEMP = 2.20
CLASS_WEIGHT = {1: 0.15, 2: 0.55, 3: 1.15, 4: 1.55}
VENUE_COURSE_BIAS = {
    "01": {1: 2.762, 2: 2.747, 3: 3.385, 4: 4.070, 5: 3.537, 6: 2.343},
    "06": {1: 2.932, 2: 3.401, 3: 3.571, 4: 3.195, 5: 2.694, 6: 2.403},
    "12": {1: 3.249, 2: 3.344, 3: 2.957, 4: 2.824, 5: 2.313, 6: 1.553},
    "18": {1: 3.509, 2: 3.116, 3: 2.908, 4: 2.648, 5: 1.380, 6: 1.355},
    "24": {1: 3.561, 2: 2.880, 3: 2.659, 4: 2.267, 5: 2.049, 6: 1.314},
}
DEFAULT_COURSE_BIAS = {1: 3.20, 2: 3.10, 3: 3.10, 4: 3.00, 5: 2.40, 6: 1.80}

BASELINE = 0.0
BALANCED = 0.20


def sf(v: Any, d: float = 0.0) -> float:
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else d
    except Exception:
        return d


def si(v: Any, d: int = 0) -> int:
    try:
        return int(float(str(v).replace(",", ""))) if v not in (None, "") else d
    except Exception:
        return d


def norm_ticket(v: Any) -> str:
    s = str(v or "")
    nums = re.findall(r"(?<!\d)([1-6])(?!\d)", s)
    if len(nums) >= 3:
        return f"{nums[0]}-{nums[1]}-{nums[2]}"
    compact = re.sub(r"\D", "", s)
    if len(compact) >= 3 and all(c in "123456" for c in compact[:3]):
        return f"{compact[0]}-{compact[1]}-{compact[2]}"
    return ""


def centered(rank: int) -> float:
    return {1: 1.0, 2: 0.6, 3: 0.2, 4: -0.2, 5: -0.6, 6: -1.0}.get(rank, 0.0)


def lane_strength(entry: Dict[str, Any], lane: int, venue: str, ex_rank: int, ex_weight: float) -> float:
    cls_w = CLASS_WEIGHT.get(si(entry.get("racer_class"), 2), 0.55)
    avg_st = sf(entry.get("avg_st"), 0.18)
    st_score = max(0.0, min(1.0, (0.24 - avg_st) / 0.12))
    course_bias = VENUE_COURSE_BIAS.get(venue, DEFAULT_COURSE_BIAS).get(
        lane, DEFAULT_COURSE_BIAS[lane]
    )
    return (
        cls_w
        + sf(entry.get("national_win_rate")) * 0.16
        + sf(entry.get("national_place2_rate"), 32.0) / 100.0 * 0.90
        + sf(entry.get("local_place2_rate"), 30.0) / 100.0 * 0.55
        + 0.33 * 0.45
        + 0.34 * 0.25
        + st_score * 0.35
        + course_bias * 0.22
        + ex_weight * centered(ex_rank)
    )


def probabilities(race: Dict[str, Any], ex_weight: float) -> Dict[str, float]:
    raw = {}
    for lane in range(1, 7):
        raw[lane] = lane_strength(
            race["entries"][lane],
            lane,
            race["venue"],
            si(race["exhibition"][lane].get("exhibition_time_rank")),
            ex_weight,
        )

    weights = {lane: math.exp(raw[lane] / TEMP) for lane in raw}
    total = sum(weights.values())
    out = {}

    for a in range(1, 7):
        pa = weights[a] / total
        remain_b = total - weights[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = weights[b] / remain_b
            remain_c = remain_b - weights[b]
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = pa * pb * weights[c] / remain_c
    return out


def prob_ranks(probs: Dict[str, float]) -> Dict[str, int]:
    return {
        t: i for i, (t, _) in enumerate(
            sorted(probs.items(), key=lambda x: x[1], reverse=True), 1
        )
    }


def market_ranks(odds: Dict[str, float]) -> Dict[str, int]:
    return {
        t: i for i, (t, _) in enumerate(
            sorted(odds.items(), key=lambda x: x[1]), 1
        )
    }


def load() -> List[Dict[str, Any]]:
    entry_rows = fetch_all(
        """
        select r.race_id, r.race_date,
               coalesce(r.venue_id,r.venue_code) as venue_id,
               r.race_no,
               e.lane, e.racer_class, e.national_win_rate,
               e.national_place2_rate, e.local_place2_rate, e.avg_st
        from v2_races r
        join v2_race_entries e on e.race_id=r.race_id
        where r.race_date between %s and %s
        order by r.race_id,e.lane;
        """,
        (START, END),
    )
    ex_rows = fetch_all(
        """
        select race_id,lane,exhibition_time_rank
        from v2_realtime_exhibition_snapshots
        where race_date between %s and %s and snapshot_label=%s;
        """,
        (START, END, LABEL),
    )
    odds_rows = fetch_all(
        """
        select race_id,ticket,odds
        from v2_realtime_odds_snapshots
        where race_date between %s and %s and snapshot_label=%s;
        """,
        (START, END, LABEL),
    )
    end_exclusive = (datetime.strptime(END, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
    result_rows = fetch_all(
        """
        select race_id,first_lane,second_lane,third_lane,
               trifecta_ticket,trifecta_payout_yen,trifecta_payout
        from v2_results
        where race_id >= %s and race_id < %s;
        """,
        (START.replace("-", ""), end_exclusive),
    )

    races: Dict[str, Dict[str, Any]] = {}
    for r in entry_rows:
        rid = str(r["race_id"])
        x = races.setdefault(
            rid,
            {
                "race_id": rid,
                "date": str(r["race_date"]),
                "venue": str(r["venue_id"]).zfill(2),
                "race_no": si(r["race_no"]),
                "entries": {},
                "exhibition": {},
                "odds": {},
                "result": "",
                "payout": 0,
            },
        )
        x["entries"][si(r["lane"])] = r

    for r in ex_rows:
        rid = str(r["race_id"])
        if rid in races:
            races[rid]["exhibition"][si(r["lane"])] = r

    for r in odds_rows:
        rid = str(r["race_id"])
        t = norm_ticket(r.get("ticket"))
        o = sf(r.get("odds"))
        if rid in races and t and o > 0:
            races[rid]["odds"][t] = o

    for r in result_rows:
        rid = str(r["race_id"])
        if rid not in races:
            continue
        a, b, c = si(r.get("first_lane")), si(r.get("second_lane")), si(r.get("third_lane"))
        races[rid]["result"] = (
            f"{a}-{b}-{c}" if all(1 <= z <= 6 for z in (a, b, c))
            else norm_ticket(r.get("trifecta_ticket"))
        )
        races[rid]["payout"] = si(
            r.get("trifecta_payout_yen"),
            si(r.get("trifecta_payout"), 0),
        )

    return [
        x for x in races.values()
        if len(x["entries"]) == 6
        and len(x["exhibition"]) == 6
        and len(x["odds"]) >= 100
        and x["result"]
    ]


def candidates(race: Dict[str, Any], ex_weight: float) -> List[Dict[str, Any]]:
    pr = prob_ranks(probabilities(race, ex_weight))
    mr = market_ranks(race["odds"])
    out = []
    for ticket, odds in race["odds"].items():
        if (
            11 <= pr.get(ticket, 999) <= 20
            and mr.get(ticket) == 1
            and 3.0 <= odds < 5.0
            and race["race_no"] <= 9
        ):
            out.append(
                {
                    "race_id": race["race_id"],
                    "date": race["date"],
                    "venue": race["venue"],
                    "race_no": race["race_no"],
                    "ticket": ticket,
                    "odds": odds,
                    "prob_rank": pr[ticket],
                    "hit": ticket == race["result"],
                    "payout": race["payout"] if ticket == race["result"] else 0,
                }
            )
    return out


def summarize(name: str, rows: List[Dict[str, Any]]) -> None:
    bets = len(rows)
    hits = sum(int(x["hit"]) for x in rows)
    investment = bets * 100
    return_yen = sum(si(x["payout"]) for x in rows)
    roi = return_yen / investment * 100 if investment else 0.0
    print(f"\n{name}", flush=True)
    print(f"  candidates={bets}", flush=True)
    print(f"  hits={hits}", flush=True)
    print(f"  hit_rate={(hits/bets*100 if bets else 0):.2f}%", flush=True)
    print(f"  investment={investment}", flush=True)
    print(f"  return={return_yen}", flush=True)
    print(f"  profit={return_yen-investment}", flush=True)
    print(f"  ROI={roi:.2f}%", flush=True)


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    print("✅ compare_exhibition_brank_roi_pg.py VERSION 2026-07-15", flush=True)
    print(f"PERIOD={START}..{END} SNAPSHOT_LABEL={LABEL}", flush=True)
    print("読み取り専用です。", flush=True)

    races = load()
    print(f"eligible_races={len(races)}", flush=True)

    base_rows: List[Dict[str, Any]] = []
    balanced_rows: List[Dict[str, Any]] = []

    for race in races:
        base_rows.extend(candidates(race, BASELINE))
        balanced_rows.extend(candidates(race, BALANCED))

    summarize("BASELINE", base_rows)
    summarize("BALANCED ex_weight=0.20", balanced_rows)

    base_keys = {(x["race_id"], x["ticket"]) for x in base_rows}
    balanced_keys = {(x["race_id"], x["ticket"]) for x in balanced_rows}

    added = [x for x in balanced_rows if (x["race_id"], x["ticket"]) not in base_keys]
    removed = [x for x in base_rows if (x["race_id"], x["ticket"]) not in balanced_keys]

    print("\nCANDIDATE CHANGES", flush=True)
    print(f"  added_by_exhibition={len(added)}", flush=True)
    print(f"  removed_by_exhibition={len(removed)}", flush=True)

    print("\nADDED SAMPLES", flush=True)
    for x in added[:SAMPLE_LIMIT]:
        print(" ", x, flush=True)

    print("\nREMOVED SAMPLES", flush=True)
    for x in removed[:SAMPLE_LIMIT]:
        print(" ", x, flush=True)

    print("\n判定目安", flush=True)
    print("- 10日分のみなのでROIの絶対値より候補の入替内容を重視", flush=True)
    print("- 候補数が極端に減る場合は、展示補正を最終判定だけに使う案も検討", flush=True)
    print("- 改善が確認できれば、次にv22へ影響しないshadow判定を追加", flush=True)
    print("=== exhibition B-rank ROI comparison finished ===", flush=True)


if __name__ == "__main__":
    main()