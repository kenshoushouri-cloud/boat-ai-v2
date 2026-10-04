# -*- coding: utf-8 -*-
"""Blind VALIDATION/OOS evaluation for frozen V5.1 Recent Form coefficient.

Candidate: V51_RECENT_FORM_LAST5_TOP3_V1
Frozen coefficient: +0.30
TRAIN freeze SHA256:
7b53c68c22ef351b85293205395938c12705ca87f03b50be9d87f196a95c3c9c

This script never searches/tunes coefficients. It freezes the pre-outcome
VALIDATION and OOS populations first, then reads only official trifecta labels.
No odds or payout data are read.
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
_v1spec = importlib.util.spec_from_file_location("candidate_v1_v51_rf_blind", V1_PATH)
v1 = importlib.util.module_from_spec(_v1spec)
assert _v1spec and _v1spec.loader
_v1spec.loader.exec_module(v1)

CONTRACT = "V51_RECENT_FORM_LAST5_TOP3_BLIND_VAL_OOS_V1"
CANDIDATE_ID = "V51_RECENT_FORM_LAST5_TOP3_V1"
COEFFICIENT = 0.30
TRAIN_FREEZE_SHA256 = "7b53c68c22ef351b85293205395938c12705ca87f03b50be9d87f196a95c3c9c"
COURSE_SOURCE = "boatrace_official_k_applied_term_proxy"
LANES = (1, 2, 3, 4, 5, 6)
LANE_SET = set(LANES)
EPS = 1e-12
JST = timezone(timedelta(hours=9))
FORWARD_CUTOFF = time(8, 15)

SPLITS = {
    "VALIDATION": {
        "start": date(2026, 1, 1),
        "end": date(2026, 6, 30),
        "course_snapshot": date(2025, 10, 31),
        "expected_population": 28178,
    },
    "OOS": {
        "start": date(2026, 7, 1),
        "end": date(2026, 9, 30),
        "course_snapshot": date(2026, 4, 30),
        "expected_population": 14492,
    },
}


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
    course_rows: dict[tuple[int, date, int], float],
    snapshot: date,
) -> dict[int, float]:
    out: dict[int, float] = {}
    for row in entries:
        lane = v1.si(row.get("lane"), 0)
        racer = v1.si(row.get("racer_number"), 0)
        value = course_rows.get((racer, snapshot, lane))
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


def load_preoutcome(
    conn: psycopg.Connection[Any],
) -> tuple[
    list[dict[str, Any]],
    dict[str, list[dict[str, Any]]],
    dict[tuple[int, date, int], float],
    dict[str, dict[str, Any]],
]:
    start = SPLITS["VALIDATION"]["start"]
    end = SPLITS["OOS"]["end"]
    with conn.cursor() as cur:
        cur.execute(
            """
            select race_id,race_date,venue_id,venue_code,race_no,deadline_at
              from v2_races
             where race_date between %s and %s
             order by race_date,venue_id,race_no,race_id
            """,
            (start, end),
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
            (start, end),
        )
        entries_by: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in cur.fetchall():
            entries_by[str(row["race_id"])].append(dict(row))

        cur.execute(
            """
            select racer_number,snapshot_date,course,top3_rate
              from v2_racer_course_stats_snapshots
             where source=%s
               and snapshot_date in (date '2025-10-31', date '2026-04-30')
               and course between 1 and 6
               and top3_rate between 0 and 100
            """,
            (COURSE_SOURCE,),
        )
        course_rows = {
            (int(x["racer_number"]), x["snapshot_date"], int(x["course"])): float(x["top3_rate"])
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
            (start, end),
        )
        opp = {str(x["race_id"]): dict(x) for x in cur.fetchall()}

    return races, entries_by, course_rows, opp


def freeze_populations(
    races: list[dict[str, Any]],
    entries_by: dict[str, list[dict[str, Any]]],
    course_rows: dict[tuple[int, date, int], float],
    opp: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {name: [] for name in SPLITS}

    for race in races:
        rid = str(race["race_id"])
        rd = _as_date(race["race_date"])
        if rd is None:
            continue
        split = next(
            (
                name for name, spec in SPLITS.items()
                if spec["start"] <= rd <= spec["end"]
            ),
            None,
        )
        if split is None:
            continue

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
        out[split].append(
            {
                "race_id": rid,
                "race_date": rd.isoformat(),
                "month": rd.strftime("%Y-%m"),
                "venue_id": venue,
                "race_no": int(race.get("race_no") or 0),
                "raw0": base_raw(entries, venue),
                "course": course_map(entries, course_rows, SPLITS[split]["course_snapshot"]),
                "motor": motor,
                "opp_delta": opponent_delta(opp.get(rid)),
                "recent_z": recent_z,
            }
        )

    for name, spec in SPLITS.items():
        expected = int(spec["expected_population"])
        actual = len(out[name])
        if actual != expected:
            raise RuntimeError(f"{name} pre-outcome population drift: {actual} != {expected}")
    return out


def load_labels(
    conn: psycopg.Connection[Any],
    populations: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, str]]:
    labels: dict[str, dict[str, str]] = {name: {} for name in SPLITS}
    with conn.cursor() as cur:
        for name, spec in SPLITS.items():
            race_ids = [x["race_id"] for x in populations[name]]
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
                (race_ids, spec["start"], spec["end"]),
            )
            for row in cur.fetchall():
                ticket = v1.norm_ticket(row["trifecta_ticket"])
                if ticket:
                    labels[name][str(row["race_id"])] = ticket
    return labels


def score_rows(
    rows: list[dict[str, Any]],
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
    month_acc: dict[str, dict[str, float]] = defaultdict(
        lambda: {"n": 0.0, "logloss_sum": 0.0, "brier_sum": 0.0, "rank_sum": 0.0}
    )
    calibration = [
        {"lo": 0.0, "hi": 0.005, "n": 0, "mean_pred_sum": 0.0},
        {"lo": 0.005, "hi": 0.010, "n": 0, "mean_pred_sum": 0.0},
        {"lo": 0.010, "hi": 0.020, "n": 0, "mean_pred_sum": 0.0},
        {"lo": 0.020, "hi": 0.040, "n": 0, "mean_pred_sum": 0.0},
        {"lo": 0.040, "hi": 1.001, "n": 0, "mean_pred_sum": 0.0},
    ]

    for row in rows:
        actual = labels.get(row["race_id"])
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
        logloss = -math.log(p_actual)

        logloss_sum += logloss
        brier_sum += brier
        rank_sum += rank
        actual_prob_sum += p_actual
        top1 += int(rank == 1)
        top2 += int(rank <= 2)
        n += 1

        ma = month_acc[row["month"]]
        ma["n"] += 1
        ma["logloss_sum"] += logloss
        ma["brier_sum"] += brier
        ma["rank_sum"] += rank

        for bucket in calibration:
            if bucket["lo"] <= p_actual < bucket["hi"]:
                bucket["n"] += 1
                bucket["mean_pred_sum"] += p_actual
                break

    if not n:
        raise RuntimeError("no official labels")

    monthly = {}
    for month, x in sorted(month_acc.items()):
        count = int(x["n"])
        monthly[month] = {
            "evaluated": count,
            "mean_logloss": x["logloss_sum"] / count,
            "mean_multiclass_brier": x["brier_sum"] / count,
            "mean_official_ticket_rank": x["rank_sum"] / count,
        }

    cal = []
    for bucket in calibration:
        count = int(bucket["n"])
        cal.append(
            {
                "range": [bucket["lo"], bucket["hi"]],
                "n": count,
                "mean_official_ticket_probability": (
                    bucket["mean_pred_sum"] / count if count else None
                ),
            }
        )

    return {
        "coefficient": coef,
        "evaluated": n,
        "mean_logloss": logloss_sum / n,
        "mean_multiclass_brier": brier_sum / n,
        "mean_official_ticket_rank": rank_sum / n,
        "mean_official_ticket_probability": actual_prob_sum / n,
        "top1_hit_rate": top1 / n,
        "top2_hit_rate": top2 / n,
        "monthly": monthly,
        "calibration_bins": cal,
    }


def gate(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    logloss_pass = candidate["mean_logloss"] < baseline["mean_logloss"]
    brier_pass = candidate["mean_multiclass_brier"] < baseline["mean_multiclass_brier"]
    rank_pass = candidate["mean_official_ticket_rank"] <= baseline["mean_official_ticket_rank"]
    return {
        "logloss_improved": logloss_pass,
        "brier_improved": brier_pass,
        "mean_rank_not_worse": rank_pass,
        "pass": logloss_pass and brier_pass and rank_pass,
        "delta_logloss": candidate["mean_logloss"] - baseline["mean_logloss"],
        "delta_brier": candidate["mean_multiclass_brier"] - baseline["mean_multiclass_brier"],
        "delta_mean_rank": candidate["mean_official_ticket_rank"] - baseline["mean_official_ticket_rank"],
    }


def main() -> None:
    output = Path(os.getenv("V51_RF_BLIND_OUTPUT", "v51-recent-form-blind-val-oos.json"))
    train_artifact = Path(
        os.getenv("V51_RF_TRAIN_ARTIFACT", "v51-recent-form-train-fit.json")
    )
    if not train_artifact.exists():
        raise RuntimeError("verified TRAIN artifact required")
    train = json.loads(train_artifact.read_text(encoding="utf-8"))
    if train.get("candidate_id") != CANDIDATE_ID:
        raise RuntimeError("unexpected TRAIN candidate")
    if train.get("freeze_sha256") != TRAIN_FREEZE_SHA256:
        raise RuntimeError("TRAIN freeze SHA mismatch")
    chosen = train.get("chosen") or {}
    if abs(float(chosen.get("coefficient")) - COEFFICIENT) > EPS:
        raise RuntimeError("TRAIN chosen coefficient mismatch")
    if train.get("validation_read") is not False or train.get("oos_read") is not False:
        raise RuntimeError("TRAIN artifact was not blind")

    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")

    print(f"V51_RF_BLIND_CONTRACT={CONTRACT}", flush=True)
    print(f"V51_RF_BLIND_COEFFICIENT={COEFFICIENT:+.2f}", flush=True)
    print(f"V51_RF_BLIND_TRAIN_FREEZE_SHA256={TRAIN_FREEZE_SHA256}", flush=True)
    print("V51_RF_BLIND_COEFFICIENT_SEARCH=0 RETUNE=0", flush=True)
    print("V51_RF_BLIND_ODDS_READ=0 PAYOUT_READ=0 DB_WRITE=0", flush=True)

    with psycopg.connect(db, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute("set local statement_timeout='180s'")
            cur.execute("set local max_parallel_workers_per_gather=0")

        inputs = load_preoutcome(conn)
        populations = freeze_populations(*inputs)
        pop_hashes = {}
        for name, rows in populations.items():
            ids = [x["race_id"] for x in rows]
            digest = hashlib.sha256(
                json.dumps(ids, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            pop_hashes[name] = digest
            print(f"V51_RF_BLIND_{name}_PREOUTCOME_POPULATION={len(rows)}", flush=True)
            print(f"V51_RF_BLIND_{name}_POPULATION_SHA256={digest}", flush=True)
        print("V51_RF_BLIND_OUTCOME_READ_BEFORE_POPULATION_FREEZE=0", flush=True)

        labels = load_labels(conn, populations)
        conn.rollback()

    split_reports = {}
    overall_pass = True
    for name in ("VALIDATION", "OOS"):
        baseline = score_rows(populations[name], labels[name], 0.0)
        candidate = score_rows(populations[name], labels[name], COEFFICIENT)
        g = gate(baseline, candidate)
        overall_pass = overall_pass and bool(g["pass"])
        split_reports[name] = {
            "population_preoutcome": len(populations[name]),
            "population_sha256": pop_hashes[name],
            "official_labels_available": len(labels[name]),
            "official_labels_unavailable": len(populations[name]) - len(labels[name]),
            "baseline": baseline,
            "candidate": candidate,
            "gate": g,
        }
        compact = {
            "split": name,
            "population": len(populations[name]),
            "labels": len(labels[name]),
            "baseline_logloss": baseline["mean_logloss"],
            "candidate_logloss": candidate["mean_logloss"],
            "baseline_brier": baseline["mean_multiclass_brier"],
            "candidate_brier": candidate["mean_multiclass_brier"],
            "baseline_rank": baseline["mean_official_ticket_rank"],
            "candidate_rank": candidate["mean_official_ticket_rank"],
            **g,
        }
        print("V51_RF_BLIND_SPLIT=" + json.dumps(compact, sort_keys=True), flush=True)

    decision = (
        "PASS_HISTORICAL_ADOPTION_GATE_FORWARD_REQUIRED"
        if overall_pass
        else "REJECT_DO_NOT_ADOPT_CONTINUE_COLLECTION"
    )
    payload = {
        "contract": CONTRACT,
        "candidate_id": CANDIDATE_ID,
        "coefficient": COEFFICIENT,
        "train_freeze_sha256": TRAIN_FREEZE_SHA256,
        "coefficient_search": False,
        "retune": False,
        "splits": split_reports,
        "historical_adoption_gate_pass": overall_pass,
        "decision": decision,
        "forward_required_if_pass": True,
        "odds_read": False,
        "payout_read": False,
        "database_write": False,
        "production_change": False,
        "promotion_allowed": False,
    }
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    payload["artifact_sha256"] = hashlib.sha256(canonical).hexdigest()
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"V51_RF_BLIND_DECISION={decision}", flush=True)
    print(f"V51_RF_BLIND_ARTIFACT_SHA256={payload['artifact_sha256']}", flush=True)
    print("V51_RF_BLIND_RESULT=PASS_EVALUATION_COMPLETED", flush=True)


if __name__ == "__main__":
    main()
