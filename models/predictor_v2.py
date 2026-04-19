# -*- coding: utf-8 -*-
from itertools import permutations
from models.feature_builder_v2 import build_entry_features


def score_ticket(ticket_lanes, feature_map):
    a, b, c = ticket_lanes
    fa = feature_map[a]
    fb = feature_map[b]
    fc = feature_map[c]

    score = (
        fa["strength"] * 0.62 +
        fb["strength"] * 0.26 +
        fc["strength"] * 0.12
    )

    if a == 1:
        score += 0.18
    elif a == 2:
        score += 0.05
    elif a >= 5:
        score -= 0.08

    if b == 1:
        score += 0.03
    elif b >= 5:
        score -= 0.03

    if c in (4, 5):
        score += 0.02

    score += fa["ex_score"] * 0.10 + fa["st_score"] * 0.08
    score += fb["ex_score"] * 0.05 + fb["st_score"] * 0.04
    score += fc["ex_score"] * 0.02 + fc["st_score"] * 0.02

    avg_weather_risk = (fa["weather_risk"] + fb["weather_risk"] + fc["weather_risk"]) / 3.0
    if avg_weather_risk > 0.55 and a >= 4:
        score -= 0.08

    return max(score, 0.0001) ** 4


def renormalize(rows):
    total = sum(x["raw_score"] for x in rows)
    if total <= 0:
        for row in rows:
            row["probability"] = 0.0
        return rows

    for row in rows:
        row["probability"] = round(row["raw_score"] / total, 6)
    return rows


def predict_race(context):
    entries = context["entries"]
    if len(entries) < 3:
        return {
            "buy_flag": False,
            "skip_reason": "entry不足",
            "feature_map": {},
            "candidates": []
        }

    feature_rows = [build_entry_features(e, context["weather"]) for e in entries]
    feature_map = {int(x["lane"]): x for x in feature_rows}

    all_candidates = []
    lanes = [1, 2, 3, 4, 5, 6]

    for combo in permutations(lanes, 3):
        ticket = f"{combo[0]}-{combo[1]}-{combo[2]}"
        odd = context["odds"].get(ticket)
        raw_score = score_ticket(combo, feature_map)

        all_candidates.append({
            "ticket": ticket,
            "raw_score": raw_score,
            "odds": odd,
        })

    # 上位候補
    all_candidates.sort(key=lambda x: x["raw_score"], reverse=True)
    top_candidates = all_candidates[:24]

    # テスト時は「オッズがある候補だけ」で再正規化
    odds_candidates = [x for x in top_candidates if x.get("odds") is not None]

    if odds_candidates:
        candidates = renormalize(odds_candidates)
        candidates.sort(key=lambda x: x["probability"], reverse=True)
    else:
        candidates = renormalize(top_candidates)
        candidates.sort(key=lambda x: x["probability"], reverse=True)

    return {
        "buy_flag": True,
        "skip_reason": None,
        "feature_map": feature_map,
        "candidates": candidates
    }
