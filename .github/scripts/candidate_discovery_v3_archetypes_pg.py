# -*- coding: utf-8 -*-
"""Candidate Discovery V3 archetype audit (READ ONLY).

V3 keeps candidate volume high without absolute odds bands or EV thresholds.
Market information is used only as a *relative rank signal* inside each race.
The system has four fixed candidate lanes inspired by distinct race structures:

- IN_STRONG_LATE_MARKET: in-strong venues, R7-R9, market-leading rank geometry
- STANDARD_LATE_MARKET: standard venues, R7-R9, market-leading rank geometry
- EARLY_MODEL: all venues, R1-R3, model-leading rank geometry
- GLOBAL_CONSENSUS: all races, model/market rank agreement

Each lane takes at most two races per day. No lane has an odds range, expected
value threshold, probability threshold, or market-rank hard gate. A ticket score
is rank-geometric and continuous. The daily union therefore targets up to eight
candidate races/tickets, with deduplication.

Historical v2_odds_trifecta is used to reconstruct market rank. This table does
not guarantee exact same-moment historical market reconstruction, so V3 is a
structure screen only; it cannot authorize Production promotion.
"""
from __future__ import annotations

import importlib.util
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
V1_PATH = HERE / "candidate_discovery_v1_pg.py"
spec = importlib.util.spec_from_file_location("candidate_discovery_v1_pg", V1_PATH)
v1 = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(v1)

JST = ZoneInfo("Asia/Tokyo")
START_DATE = os.getenv("CANDIDATE_DISCOVERY_V3_START", "2025-07-01").strip()
END_DATE = os.getenv(
    "CANDIDATE_DISCOVERY_V3_END",
    (datetime.now(JST).date() - timedelta(days=1)).isoformat(),
).strip()
OUTPUT = Path(os.getenv("CANDIDATE_DISCOVERY_V3_OUTPUT", "candidate-discovery-v3-archetypes.json"))
UNIT_YEN = max(1, int(os.getenv("CANDIDATE_DISCOVERY_V3_UNIT_YEN", "100")))
PER_LANE_DAILY_CAP = 2
ALL_LANES = {1, 2, 3, 4, 5, 6}
BAD5 = {"01", "04", "05", "06", "23"}
ROUGH = {"02", "03", "04", "05", "06"}
IN_STRONG = {"12", "15", "18", "21", "24"}

LANE_SPECS = (
    ("IN_STRONG_LATE_MARKET", "market_lead"),
    ("STANDARD_LATE_MARKET", "market_lead"),
    ("EARLY_MODEL", "model_lead"),
    ("GLOBAL_CONSENSUS", "consensus"),
)


def next_day(ds: str) -> str:
    return (datetime.strptime(ds, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")


def month_starts(start: str, end: str):
    d = datetime.strptime(start[:7] + "-01", "%Y-%m-%d")
    e = datetime.strptime(end[:7] + "-01", "%Y-%m-%d")
    while d <= e:
        yield d.strftime("%Y-%m-%d")
        d = d.replace(year=d.year + 1, month=1) if d.month == 12 else d.replace(month=d.month + 1)


def next_month(ds: str) -> str:
    d = datetime.strptime(ds, "%Y-%m-%d")
    d = d.replace(year=d.year + 1, month=1) if d.month == 12 else d.replace(month=d.month + 1)
    return d.strftime("%Y-%m-%d")


def venue_style(venue: str) -> str:
    v = str(venue).zfill(2)
    if v in BAD5:
        return "bad5"
    if v in ROUGH:
        return "rough"
    if v in IN_STRONG:
        return "in_strong"
    return "standard"


def validate_odds(odds: dict[str, float]) -> bool:
    if len(odds) != 120:
        return False
    expected = {
        f"{a}-{b}-{c}"
        for a in range(1, 7)
        for b in range(1, 7)
        for c in range(1, 7)
        if len({a, b, c}) == 3
    }
    return set(odds) == expected and all(float(value) > 0 for value in odds.values())


def ranks(values: dict[str, float], reverse: bool) -> dict[str, int]:
    if reverse:
        ordered = sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))
    else:
        ordered = sorted(values.items(), key=lambda kv: (kv[1], kv[0]))
    return {ticket: idx for idx, (ticket, _) in enumerate(ordered, 1)}


def ticket_score(prob_rank: int, market_rank: int, mode: str, n: int = 120) -> float:
    # Continuous rank geometry only. No hard rank/odds/EV gate.
    model_q = (n - prob_rank + 1) / n
    market_q = (n - market_rank + 1) / n
    span = max(1, n - 1)
    if mode == "market_lead":
        lead_q = ((prob_rank - market_rank) + span) / (2 * span)
        return math.sqrt(max(0.0, market_q) * max(0.0, lead_q))
    if mode == "model_lead":
        lead_q = ((market_rank - prob_rank) + span) / (2 * span)
        return math.sqrt(max(0.0, model_q) * max(0.0, lead_q))
    if mode == "consensus":
        return math.sqrt(max(0.0, model_q) * max(0.0, market_q))
    raise ValueError(mode)


def pick_ticket(probs: dict[str, float], odds: dict[str, float], mode: str) -> dict[str, Any]:
    pr = ranks(probs, reverse=True)
    mr = ranks(odds, reverse=False)
    best = None
    for ticket in probs:
        score = ticket_score(pr[ticket], mr[ticket], mode)
        item = {
            "ticket": ticket,
            "score": score,
            "prob": float(probs[ticket]),
            "prob_rank": pr[ticket],
            "market_rank": mr[ticket],
            "market_lead": pr[ticket] - mr[ticket],
            "model_lead": mr[ticket] - pr[ticket],
        }
        if best is None or (
            item["score"], item["prob"], -item["prob_rank"], item["ticket"]
        ) > (
            best["score"], best["prob"], -best["prob_rank"], best["ticket"]
        ):
            best = item
    assert best is not None
    return best


def lane_matches(lane_id: str, venue: str, race_no: int) -> bool:
    style = venue_style(venue)
    if lane_id == "IN_STRONG_LATE_MARKET":
        return style == "in_strong" and 7 <= race_no <= 9
    if lane_id == "STANDARD_LATE_MARKET":
        return style == "standard" and 7 <= race_no <= 9
    if lane_id == "EARLY_MODEL":
        return 1 <= race_no <= 3
    if lane_id == "GLOBAL_CONSENSUS":
        return True
    return False


def evaluate(rows: list[dict[str, Any]], results: dict[str, tuple[str, int]]) -> dict[str, Any]:
    evaluated = hits = pending = investment = returns = 0
    losing = max_losing = 0
    by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sorted(rows, key=lambda x: (x["race_date"], x["venue_id"], x["race_no"], x["lane_id"])):
        result = results.get(str(row["race_id"]))
        if result is None:
            pending += 1
            continue
        win_ticket, payout = result
        evaluated += 1
        investment += UNIT_YEN
        hit = row["ticket"] == win_ticket
        ret = payout if hit else 0
        returns += ret
        if hit:
            hits += 1
            losing = 0
        else:
            losing += 1
            max_losing = max(max_losing, losing)
        by_month[row["race_date"][:7]].append({"hit": hit, "return": ret})
    monthly = {}
    for month, rr in sorted(by_month.items()):
        inv = len(rr) * UNIT_YEN
        ret = sum(int(x["return"]) for x in rr)
        mh = sum(1 for x in rr if x["hit"])
        monthly[month] = {
            "evaluated": len(rr),
            "hits": mh,
            "hit_rate_pct": round(mh / len(rr) * 100.0, 3) if rr else None,
            "return_yen": ret,
            "investment_yen": inv,
            "profit_yen": ret - inv,
            "roi_pct": round(ret / inv * 100.0, 3) if inv else None,
        }
    return {
        "selected": len(rows),
        "evaluated": evaluated,
        "pending": pending,
        "hits": hits,
        "hit_rate_pct": round(hits / evaluated * 100.0, 3) if evaluated else None,
        "investment_yen": investment,
        "return_yen": returns,
        "profit_yen": returns - investment,
        "roi_pct": round(returns / investment * 100.0, 3) if investment else None,
        "max_losing_streak": max_losing,
        "monthly": monthly,
    }


def dedupe_union(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Keep one exact race/ticket bet, preserve all lane tags for audit.
    by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["race_id"]), str(row["ticket"]))
        if key not in by_key:
            item = dict(row)
            item["lane_ids"] = [str(row["lane_id"])]
            by_key[key] = item
        elif str(row["lane_id"]) not in by_key[key]["lane_ids"]:
            by_key[key]["lane_ids"].append(str(row["lane_id"]))
    return list(by_key.values())


def load_month(conn, a: str, b: str):
    ra, rb = a.replace("-", ""), b.replace("-", "")
    with conn.cursor() as cur:
        cur.execute(
            """select race_id,race_date,venue_id,venue_code,race_no
                 from v2_races where race_date >= %s and race_date < %s
                 order by race_date,venue_id,race_no,race_id""",
            (a, b),
        )
        races = [dict(row) for row in cur.fetchall()]
        cur.execute(
            """select race_id,lane,racer_class,national_win_rate,national_place2_rate,
                      local_place2_rate,avg_st,motor_place2_rate
                 from v2_race_entries
                where race_id >= %s and race_id < %s
                order by race_id,lane""",
            (ra, rb),
        )
        entries = defaultdict(list)
        for row in cur.fetchall():
            entries[str(row["race_id"])].append(dict(row))
        cur.execute(
            """select race_id,ticket,odds from v2_odds_trifecta
                where race_id >= %s and race_id < %s and odds > 0
                order by race_id,ticket""",
            (ra, rb),
        )
        odds_by: dict[str, dict[str, float]] = defaultdict(dict)
        for row in cur.fetchall():
            ticket = v1.norm_ticket(row["ticket"])
            odd = v1.sf(row["odds"], None)
            if ticket and odd and odd > 0:
                odds_by[str(row["race_id"])][ticket] = float(odd)
        cur.execute(
            """select race_id,trifecta_ticket,trifecta_payout_yen
                 from v2_results
                where race_date >= %s and race_date < %s
                  and result_status='official' and race_status='official'
                  and trifecta_ticket is not null and trifecta_payout_yen > 0
                order by race_id""",
            (a, b),
        )
        results = {}
        for row in cur.fetchall():
            ticket = v1.norm_ticket(row["trifecta_ticket"])
            payout = v1.si(row["trifecta_payout_yen"], 0)
            if ticket and payout > 0:
                results[str(row["race_id"])] = (ticket, payout)
    return races, entries, odds_by, results


def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    print("CANDIDATE_DISCOVERY_V3_MODE=multi_archetype_relative_market_rank", flush=True)
    print(f"CANDIDATE_DISCOVERY_V3_PERIOD={START_DATE}..{END_DATE}", flush=True)
    print("CANDIDATE_DISCOVERY_V3_ABSOLUTE_ODDS_FILTER=0 EV_FILTER=0 PROB_FILTER=0 MARKET_RANK_GATE=0", flush=True)
    print(f"CANDIDATE_DISCOVERY_V3_PER_LANE_DAILY_CAP={PER_LANE_DAILY_CAP} lanes:{len(LANE_SPECS)}", flush=True)
    print("CANDIDATE_DISCOVERY_V3_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)
    print("CANDIDATE_DISCOVERY_V3_TIMING_CAVEAT=historical_odds_snapshot_not_exact_same_moment", flush=True)

    lane_rows: dict[str, list[dict[str, Any]]] = {lane_id: [] for lane_id, _ in LANE_SPECS}
    results_all: dict[str, tuple[str, int]] = {}
    audit = {"races": 0, "complete_entries": 0, "complete_odds": 0, "evaluated_model_races": 0}

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local lock_timeout='5s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

        for month in month_starts(START_DATE, END_DATE):
            a = max(START_DATE, month)
            b = min(next_day(END_DATE), next_month(month))
            if a >= b:
                continue
            races, entries_by, odds_by, results = load_month(conn, a, b)
            results_all.update(results)
            audit["races"] += len(races)
            candidates_by_day_lane: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
            for race in races:
                race_id = str(race.get("race_id") or "")
                entries = entries_by.get(race_id, [])
                if len(entries) != 6 or {v1.si(row.get("lane"), 0) for row in entries} != ALL_LANES:
                    continue
                audit["complete_entries"] += 1
                odds = odds_by.get(race_id, {})
                if not validate_odds(odds):
                    continue
                audit["complete_odds"] += 1
                venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
                race_no = v1.si(race.get("race_no"), 0)
                race_date = str(race.get("race_date") or "")[:10]
                probs = v1.ticket_probabilities(entries, venue, 0.0)
                audit["evaluated_model_races"] += 1
                for lane_id, mode in LANE_SPECS:
                    if not lane_matches(lane_id, venue, race_no):
                        continue
                    picked = pick_ticket(probs, odds, mode)
                    picked.update(
                        {
                            "lane_id": lane_id,
                            "race_id": race_id,
                            "race_date": race_date,
                            "venue_id": venue,
                            "venue_style": venue_style(venue),
                            "race_no": race_no,
                            "mode": mode,
                        }
                    )
                    candidates_by_day_lane[(race_date, lane_id)].append(picked)

            for (race_date, lane_id), rows in candidates_by_day_lane.items():
                rows.sort(
                    key=lambda row: (
                        -float(row["score"]),
                        -float(row["prob"]),
                        int(row["prob_rank"]),
                        str(row["race_id"]),
                    )
                )
                lane_rows[lane_id].extend(rows[:PER_LANE_DAILY_CAP])

        conn.rollback()

    lane_reports = {}
    for lane_id, _ in LANE_SPECS:
        report = evaluate(lane_rows[lane_id], results_all)
        lane_reports[lane_id] = report
        print(
            f"CANDIDATE_DISCOVERY_V3_LANE={lane_id} selected:{report['selected']} "
            f"eval:{report['evaluated']} hits:{report['hits']} hit_rate:{report['hit_rate_pct']} "
            f"roi:{report['roi_pct']} max_lose:{report['max_losing_streak']}",
            flush=True,
        )

    union_rows = dedupe_union([row for lane_id in lane_rows for row in lane_rows[lane_id]])
    union_report = evaluate(union_rows, results_all)
    by_day = defaultdict(int)
    for row in union_rows:
        by_day[row["race_date"]] += 1
    volume = {
        "days": len(by_day),
        "mean_candidates_per_day": round(sum(by_day.values()) / len(by_day), 3) if by_day else 0.0,
        "min_candidates_per_day": min(by_day.values()) if by_day else 0,
        "max_candidates_per_day": max(by_day.values()) if by_day else 0,
    }
    print(
        f"CANDIDATE_DISCOVERY_V3_UNION=selected:{union_report['selected']} eval:{union_report['evaluated']} "
        f"hits:{union_report['hits']} roi:{union_report['roi_pct']} avg_day:{volume['mean_candidates_per_day']} "
        f"max_lose:{union_report['max_losing_streak']}",
        flush=True,
    )

    out = {
        "contract": "candidate_discovery_v3_multi_archetype_relative_market_rank",
        "period": {"start": START_DATE, "end": END_DATE},
        "selection": {
            "absolute_odds_filter": False,
            "expected_value_filter": False,
            "probability_filter": False,
            "market_rank_hard_gate": False,
            "market_usage": "relative rank signal only",
            "per_lane_daily_cap": PER_LANE_DAILY_CAP,
            "lanes": [{"lane_id": lane_id, "mode": mode} for lane_id, mode in LANE_SPECS],
        },
        "historical_timing_caveat": "v2_odds_trifecta does not guarantee exact same-moment historical market reconstruction",
        "audit": audit,
        "lane_reports": lane_reports,
        "union_volume": volume,
        "union_report": union_report,
        "mutation_performed": False,
        "line_sent": False,
        "purchase_action": False,
        "production_behavior_changed": False,
        "promotion_allowed": False,
    }
    OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CANDIDATE_DISCOVERY_V3_AUDIT=" + json.dumps(audit, sort_keys=True), flush=True)
    print("CANDIDATE_DISCOVERY_V3_PURCHASE_ACTION=false", flush=True)
    print("CANDIDATE_DISCOVERY_V3_PROMOTION_ALLOWED=0", flush=True)
    print("CANDIDATE_DISCOVERY_V3_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
