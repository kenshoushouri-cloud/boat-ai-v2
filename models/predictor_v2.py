# -*- coding: utf-8 -*-
from models.feature_builder_v2 import build_entry_features


def _first_lane_multiplier(lane):
    lane = int(lane)
    table = {
        1: 1.08,
        2: 1.03,
        3: 1.00,
        4: 0.97,
        5: 0.91,
        6: 0.85,
    }
    return table.get(lane, 1.0)


def _second_lane_multiplier(lane):
    lane = int(lane)
    table = {
        1: 0.95,
        2: 1.00,
        3: 1.06,
        4: 1.10,
        5: 1.03,
        6: 0.94,
    }
    return table.get(lane, 1.0)


def _third_lane_multiplier(lane):
    lane = int(lane)
    table = {
        1: 0.82,
        2: 0.90,
        3: 1.06,
        4: 1.14,
        5: 1.14,
        6: 1.05,
    }
    return table.get(lane, 1.0)


def _build_role_rows(feature_rows):
    rows = []

    for row in feature_rows:
        lane = int(row["lane"])
        base = float(row["score"])

        first_score = max(base * _first_lane_multiplier(lane), 0.0001)
        second_score = max(base * _second_lane_multiplier(lane), 0.0001)
        third_score = max(base * _third_lane_multiplier(lane), 0.0001)

        rows.append({
            "lane": lane,
            "base_score": round(base, 6),
            "first_score": round(first_score, 6),
            "second_score": round(second_score, 6),
            "third_score": round(third_score, 6),
        })

    return rows


def _normalize_candidates(candidates):
    total = sum(c["raw_score"] for c in candidates)

    out = []
    for c in candidates:
        prob = (c["raw_score"] / total) if total > 0 else 0.0
        row = dict(c)
        row["probability"] = round(prob, 6)
        out.append(row)

    out.sort(key=lambda x: x["probability"], reverse=True)
    return out


def _build_exacta_candidates(trifecta_candidates):
    exacta_map = {}

    for c in trifecta_candidates:
        first_lane = c["first_lane"]
        second_lane = c["second_lane"]
        ticket = f"{first_lane}-{second_lane}"
        prob = c.get("probability", 0.0)

        if ticket not in exacta_map:
            exacta_map[ticket] = {
                "ticket": ticket,
                "first_lane": first_lane,
                "second_lane": second_lane,
                "probability": 0.0,
            }

        exacta_map[ticket]["probability"] += prob

    exacta_candidates = list(exacta_map.values())
    exacta_candidates.sort(key=lambda x: x["probability"], reverse=True)

    for row in exacta_candidates:
        row["probability"] = round(row["probability"], 6)

    return exacta_candidates


def _calc_race_score(trifecta_candidates, exacta_candidates):
    tri_top1 = trifecta_candidates[0]["probability"] if len(trifecta_candidates) >= 1 else 0.0
    tri_top2 = trifecta_candidates[1]["probability"] if len(trifecta_candidates) >= 2 else 0.0
    ex_top1 = exacta_candidates[0]["probability"] if len(exacta_candidates) >= 1 else 0.0
    ex_top2 = exacta_candidates[1]["probability"] if len(exacta_candidates) >= 2 else 0.0

    score = (
        (ex_top1 * 1.8) +
        (ex_top2 * 0.8) +
        (tri_top1 * 0.8) +
        ((ex_top1 - ex_top2) * 3.0) +
        ((tri_top1 - tri_top2) * 2.0)
    )

    return round(score, 6)


def predict_race(context):
    feature_rows = build_entry_features(context)

    if len(feature_rows) < 3:
        return {
            "race_id": context.get("race_id"),
            "entries": feature_rows,
            "candidates": [],
            "exacta_candidates": [],
            "race_score": 0.0,
        }

    role_rows = _build_role_rows(feature_rows)
    trifecta_candidates = []

    for first in role_rows:
        for second in role_rows:
            if second["lane"] == first["lane"]:
                continue

            for third in role_rows:
                if third["lane"] in (first["lane"], second["lane"]):
                    continue

                ticket = f"{first['lane']}-{second['lane']}-{third['lane']}"

                raw_score = (
                    first["first_score"] *
                    second["second_score"] *
                    third["third_score"]
                )

                trifecta_candidates.append({
                    "ticket": ticket,
                    "raw_score": round(raw_score, 12),
                    "first_lane": first["lane"],
                    "second_lane": second["lane"],
                    "third_lane": third["lane"],
                })

    trifecta_candidates = _normalize_candidates(trifecta_candidates)
    exacta_candidates = _build_exacta_candidates(trifecta_candidates)
    race_score = _calc_race_score(trifecta_candidates, exacta_candidates)

    odds_map = context.get("odds", {}) or {}
    for c in trifecta_candidates:
        odds = odds_map.get(c["ticket"])
        c["odds"] = odds
        c["ev"] = round(c["probability"] * odds, 3) if odds is not None else None

    return {
        "race_id": context.get("race_id"),
        "entries": feature_rows,
        "candidates": trifecta_candidates,
        "exacta_candidates": exacta_candidates,
        "race_score": race_score,
    }
