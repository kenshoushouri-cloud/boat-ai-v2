# -*- coding: utf-8 -*-
"""TRAIN-only coefficient fit for V51_RECENT_FORM_LAST5_TOP3_V1.

This script intentionally reads outcomes only for TRAIN_REFERENCE
(2025-07-01..2025-12-31). VALIDATION and OOS are not queried.

The coefficient grid and tie-breaking are frozen in:
docs/V51_RECENT_FORM_COEFFICIENT_SEARCH_LOCK_20261004.md
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from research import candidate_discovery_v4_contract as v4

ROOT = Path(__file__).resolve().parents[1]
V1_PATH = ROOT / ".github" / "scripts" / "candidate_discovery_v1_pg.py"
_v1spec = importlib.util.spec_from_file_location("candidate_v1_v51_rf_train_fit", V1_PATH)
v1 = importlib.util.module_from_spec(_v1spec)
assert _v1spec and _v1spec.loader
_v1spec.loader.exec_module(v1)

CONTRACT = "V51_RECENT_FORM_LAST5_TOP3_TRAIN_FIT_V1"
CANDIDATE_ID = "V51_RECENT_FORM_LAST5_TOP3_V1"
TRAIN_START = date(2025, 7, 1)
TRAIN_END = date(2025, 12, 31)
COURSE_SOURCE = "boatrace_official_k_applied_term_proxy"
COURSE_SNAPSHOT = date(2025, 4, 30)
GRID = (-0.50, -0.40, -0.30, -0.20, -0.10, 0.00, 0.10, 0.20, 0.30, 0.40, 0.50)
EXPECTED_PREOUTCOME_POPULATION = 26801
LANES = (1, 2, 3, 4, 5, 6)
LANE_SET = set(LANES)
EPS = 1e-12
JST = timezone(timedelta(hours=9))
FORWARD_CUTOFF = time(8, 15)


def _finite(v: Any) -> float | None:
    try:
        x = float(v)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def _as_date(v: Any) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def _aware_jst(v: Any) -> datetime | None:
    if not isinstance(v, datetime):
        return None
    if v.tzinfo is None or v.utcoffset() is None:
        v = v.replace(tzinfo=JST)
    return v.astimezone(JST)


def opponent_usable(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    rd = _as_date(row.get("race_date"))
    te = _as_date(row.get("train_end"))
    if rd is None or te is None or te >= rd:
        return False
    matched = row.get("matched_opponents")
    base = row.get("base_win")
    adj = row.get("adj_win")
    if not all(isinstance(x, list) and len(x) == 6 for x in (matched, base, adj)):
        return False
    try:
        if any(int(x) < 4 for x in matched):
            return False
    except Exception:
        return False
    if any(_finite(x) is None for x in base) or any(_finite(x) is None for x in adj):
        return False

    version = int(row.get("model_version") or 0)
    if version == 102:
        return True
    if version != 2:
        return False

    created = _aware_jst(row.get("created_at"))
    updated = _aware_jst(row.get("updated_at"))
    deadline = _aware_jst(row.get("deadline_at"))
    if created is None or updated is None or deadline is None:
        return False
    cutoff = datetime.combine(rd, FORWARD_CUTOFF, tzinfo=JST)
    return created < cutoff and updated < cutoff and created < deadline and updated < deadline


def opponent_delta(row: dict[str, Any] | None) -> dict[int, float] | None:
    if not opponent_usable(row):
        return None
    base = row["base_win"]
    adj = row["adj_win"]
    return {lane: float(adj[lane - 1]) - float(base[lane - 1]) for lane in LANES}


def base_raw(entries: list[dict[str, Any]], venue: str) -> dict[int, float]:
    by = {v1.si(r.get("lane"), 0): r for r in entries}
    if set(by) != LANE_SET:
        raise ValueError("exact six lanes required")
    return {
        lane: v1.lane_raw_strength(by[lane], lane, venue, 0.0)
        for lane in LANES
    }


def motor_map(entries: list[dict[str, Any]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for row in entries:
        lane = v1.si(row.get("lane"), 0)
        value = _finite(row.get("motor_place2_rate"))
        if lane not in LANE_SET or value is None or not 0.0 <= value <= 100.0:
            return {}
        out[lane] = value
    return out if set(out) == LANE_SET else {}


def course_map(
    entries: list[dict[str, Any]],
    course_rows: dict[tuple[int, int], float],
) -> dict[int, float]:
    out: dict[int, float] = {}
    for row in entries:
        lane = v1.si(row.get("lane"), 0)
        racer = v1.si(row.get("racer_number"), 0)
        value = course_rows.get((racer, lane))
        if racer > 0 and lane in LANE_SET and value is not None:
            out[lane] = value
    return out


def recent_feature(entries: list[dict[str, Any]], target_date: date) -> dict[int, float]:
    rates: dict[int, float] = {}
    for row in entries:
        lane = v1.si(row.get("lane"), 0)
        rf = row.get("recent_form")
        if lane not in LANE_SET or not isinstance(rf, list) or not 1 <= len(rf) <= 5:
            continue

        valid = 0
        top3 = 0
        provenance_ok = True
        for item in rf:
            if not isinstance(item, dict) or item.get("source") != "official_k_file":
                provenance_ok = False
                break
            ds = str(item.get("race_date") or "")
            try:
                hist_date = date.fromisoformat(ds)
            except ValueError:
                provenance_ok = False
                break
            if hist_date >= target_date:
                provenance_ok = False
                break
            finish = v1.si(item.get("finish_position"), 0)
            if 1 <= finish <= 6:
                valid += 1
                top3 += int(finish <= 3)

        if provenance_ok and valid >= 3:
            rates[lane] = top3 / valid

    if len(rates) < 2:
        return {}
    xs = list(rates.values())
    mean = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs))
    if sd <= EPS:
        return {}
    return {lane: (value - mean) / sd for lane, value in rates.items()}


def distribution(
    *,
    raw0: dict[int, float],
    course: dict[int, float],
    motor: dict[int, float],
    opp_delta: dict[int, float] | None,
    recent_z: dict[int, float],
    coef: float,
) -> dict[str, float]:
    raw = v4.course_adjust_raw(raw0, course)
    adjusted_raw = {
        lane: float(raw[lane]) + float(coef) * float(recent_z.get(lane, 0.0))
        for lane in LANES
    }
    base_lane = v4.lane_probabilities(adjusted_raw)
    adjusted_first = v4.opponent_adjust_first_probs(base_lane, opp_delta)
    probs = v4.head_only_trifecta(base_lane, adjusted_first)
    return v4.motor_adjust(probs, motor)


def load_preoutcome(conn: psycopg.Connection[Any]) -> tuple[
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[tuple[int, int], float],
    dict[str, dict[str, Any]],
]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,race_date,venue_id,venue_code,race_no,deadline_at
              from v2_races
             where race_date between %s and %s
             order by race_date,venue_id,race_no,race_id
            """,
            (TRAIN_START, TRAIN_END),
        )
        races = [dict(x) for x in cur.fetchall()]

        cur.execute(
            """
            select e.race_id,e.lane,e.racer_number,e.racer_class,
                   e.national_win_rate,e.national_place2_rate,
                   e.local_place2_rate,e.avg_st,e.motor_place2_rate,
                   e.recent_form
              from v2_race_entries e
              join v2_races r on r.race_id=e.race_id
             where r.race_date between %s and %s
             order by e.race_id,e.lane
            """,
            (TRAIN_START, TRAIN_END),
        )
        entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cur.fetchall():
            entries_by[str(row["race_id"])].append(dict(row))

        cur.execute(
            """
            select racer_number,course,top3_rate
              from v2_racer_course_stats_snapshots
             where source=%s
               and snapshot_date=%s
               and course between 1 and 6
               and top3_rate between 0 and 100
            """,
            (COURSE_SOURCE, COURSE_SNAPSHOT),
        )
        course_rows = {
            (int(x["racer_number"]), int(x["course"])): float(x["top3_rate"])
            for x in cur.fetchall()
        }

        cur.execute(
            """
            select s.race_id,s.race_date,s.model_version,s.train_end,
                   s.matched_opponents,s.base_win,s.adj_win,
                   s.created_at,s.updated_at,r.deadline_at
              from v2_opponent_pressure_shadow_v2 s
              join v2_races r on r.race_id=s.race_id
             where s.race_date between %s and %s
             order by s.race_date,s.race_id
            """,
            (TRAIN_START, TRAIN_END),
        )
        opp = {str(x["race_id"]): dict(x) for x in cur.fetchall()}

    return races, entries_by, course_rows, opp


def freeze_train_population(
    races: list[dict[str, Any]],
    entries_by: dict[str, list[dict[str, Any]]],
    course_rows: dict[tuple[int, int], float],
    opp: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for race in races:
        rid = str(race["race_id"])
        rd = race["race_date"]
        if isinstance(rd, str):
            rd = date.fromisoformat(rd)
        if not TRAIN_START <= rd <= TRAIN_END:
            raise RuntimeError("non-TRAIN race reached fitter")

        entries = entries_by.get(rid, [])
        if len(entries) != 6 or {v1.si(x.get("lane"), 0) for x in entries} != LANE_SET:
            continue
        motor = motor_map(entries)
        if not motor:
            continue
        recent_z = recent_feature(entries, rd)
        if not recent_z:
            continue

        venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
        out.append(
            {
                "race_id": rid,
                "race_date": rd.isoformat(),
                "venue_id": venue,
                "race_no": int(race.get("race_no") or 0),
                "raw0": base_raw(entries, venue),
                "course": course_map(entries, course_rows),
                "motor": motor,
                "opp_delta": opponent_delta(opp.get(rid)),
                "recent_z": recent_z,
            }
        )

    if len(out) != EXPECTED_PREOUTCOME_POPULATION:
        raise RuntimeError(
            f"pre-outcome TRAIN population drift: {len(out)} != "
            f"{EXPECTED_PREOUTCOME_POPULATION}"
        )
    return out


def load_train_labels(
    conn: psycopg.Connection[Any],
    race_ids: list[str],
) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            select vr.race_id,vr.trifecta_ticket
              from v2_results vr
              join v2_races r on r.race_id=vr.race_id
             where vr.race_id=any(%s)
               and r.race_date between %s and %s
               and vr.result_status='official'
               and vr.race_status='official'
               and vr.trifecta_ticket is not null
             order by vr.race_id
            """,
            (race_ids, TRAIN_START, TRAIN_END),
        )
        out: dict[str, str] = {}
        for row in cur.fetchall():
            ticket = v1.norm_ticket(row["trifecta_ticket"])
            if ticket:
                out[str(row["race_id"])] = ticket
    return out


def metrics_for_coef(
    frozen: list[dict[str, Any]],
    labels: dict[str, str],
    coef: float,
) -> dict[str, Any]:
    logloss_sum = 0.0
    brier_sum = 0.0
    rank_sum = 0.0
    actual_prob_sum = 0.0
    top1 = 0
    top2 = 0
    n = 0

    for row in frozen:
        rid = row["race_id"]
        actual = labels.get(rid)
        if not actual:
            continue
        probs = distribution(
            raw0=row["raw0"],
            course=row["course"],
            motor=row["motor"],
            opp_delta=row["opp_delta"],
            recent_z=row["recent_z"],
            coef=coef,
        )
        p_actual = max(EPS, float(probs.get(actual, 0.0)))
        ranked = sorted(probs.items(), key=lambda kv: (-float(kv[1]), kv[0]))
        rank = next(i for i, (ticket, _) in enumerate(ranked, 1) if ticket == actual)
        brier = sum(
            (float(prob) - (1.0 if ticket == actual else 0.0)) ** 2
            for ticket, prob in probs.items()
        )

        logloss_sum += -math.log(p_actual)
        brier_sum += brier
        rank_sum += rank
        actual_prob_sum += p_actual
        top1 += int(rank == 1)
        top2 += int(rank <= 2)
        n += 1

    if not n:
        raise RuntimeError("no scoreable TRAIN labels")
    return {
        "coefficient": round(float(coef), 2),
        "evaluated": n,
        "mean_logloss": logloss_sum / n,
        "mean_multiclass_brier": brier_sum / n,
        "mean_official_ticket_rank": rank_sum / n,
        "mean_official_ticket_probability": actual_prob_sum / n,
        "top1_hit_rate": top1 / n,
        "top2_hit_rate": top2 / n,
    }


def choose(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    best = metrics[0]
    for row in metrics[1:]:
        delta = float(row["mean_logloss"]) - float(best["mean_logloss"])
        if delta < -1e-12:
            best = row
        elif abs(delta) <= 1e-12:
            c = float(row["coefficient"])
            b = float(best["coefficient"])
            if abs(c) < abs(b) or (abs(c) == abs(b) and c < b):
                best = row
    return dict(best)


def main() -> None:
    output = Path(os.getenv("V51_RF_TRAIN_FIT_OUTPUT", "v51-recent-form-train-fit.json"))
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V51_RF_TRAIN_FIT_CONTRACT={CONTRACT}", flush=True)
    print(f"V51_RF_TRAIN_FIT_PERIOD={TRAIN_START}..{TRAIN_END}", flush=True)
    print("V51_RF_TRAIN_FIT_VALIDATION_READ=0 OOS_READ=0", flush=True)
    print("V51_RF_TRAIN_FIT_ODDS_READ=0 PAYOUT_READ=0 DB_WRITE=0", flush=True)
    print("V51_RF_TRAIN_FIT_GRID=" + json.dumps(GRID), flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

        inputs = load_preoutcome(conn)
        frozen = freeze_train_population(*inputs)

        freeze_ids = [x["race_id"] for x in frozen]
        population_sha = hashlib.sha256(
            json.dumps(freeze_ids, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        print(f"V51_RF_TRAIN_FIT_PREOUTCOME_POPULATION={len(frozen)}", flush=True)
        print(f"V51_RF_TRAIN_FIT_POPULATION_SHA256={population_sha}", flush=True)
        print("V51_RF_TRAIN_FIT_OUTCOME_READ_BEFORE_FREEZE=0", flush=True)

        labels = load_train_labels(conn, freeze_ids)
        conn.rollback()

    metrics = [metrics_for_coef(frozen, labels, coef) for coef in GRID]
    chosen = choose(metrics)
    baseline = next(x for x in metrics if abs(float(x["coefficient"])) <= EPS)

    payload: dict[str, Any] = {
        "contract": CONTRACT,
        "candidate_id": CANDIDATE_ID,
        "train_period": [TRAIN_START.isoformat(), TRAIN_END.isoformat()],
        "coefficient_grid": list(GRID),
        "population_preoutcome": len(frozen),
        "population_sha256": population_sha,
        "official_labels_available": len(labels),
        "official_labels_unavailable": len(frozen) - len(labels),
        "selection_objective": "minimum_mean_official_trifecta_multiclass_logloss",
        "tie_rule": "within_1e-12_then_smaller_abs_coef_then_smaller_numeric_coef",
        "metrics": metrics,
        "baseline": baseline,
        "chosen": chosen,
        "decision": "REJECT_HOLD_ZERO_WON" if abs(float(chosen["coefficient"])) <= EPS else "COEFFICIENT_FROZEN_FOR_BLIND_VALIDATION_OOS",
        "validation_read": False,
        "oos_read": False,
        "odds_read": False,
        "payout_read": False,
        "database_write": False,
        "production_change": False,
        "promotion_allowed": False,
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    payload["freeze_sha256"] = hashlib.sha256(canonical).hexdigest()

    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    for row in metrics:
        print("V51_RF_TRAIN_FIT_METRIC=" + json.dumps(row, sort_keys=True), flush=True)
    print("V51_RF_TRAIN_FIT_BASELINE=" + json.dumps(baseline, sort_keys=True), flush=True)
    print("V51_RF_TRAIN_FIT_CHOSEN=" + json.dumps(chosen, sort_keys=True), flush=True)
    print(f"V51_RF_TRAIN_FIT_LABELS={len(labels)}/{len(frozen)}", flush=True)
    print(f"V51_RF_TRAIN_FIT_FREEZE_SHA256={payload['freeze_sha256']}", flush=True)
    print(f"V51_RF_TRAIN_FIT_DECISION={payload['decision']}", flush=True)
    print("V51_RF_TRAIN_FIT_RESULT=PASS_TRAIN_ONLY_FROZEN", flush=True)


if __name__ == "__main__":
    main()
