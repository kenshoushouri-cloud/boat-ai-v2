# -*- coding: utf-8 -*-

def build_filter_config(analysis):
    """
    analysis結果から勝てる条件を自動抽出
    """

    config = {
        "min_score": 0.0,
        "min_prob": 0.0,
        "allowed_venues": [],
        "allowed_bet_types": []
    }

    # ---------------------------
    # score帯
    # ---------------------------
    best_score = None
    best_roi = -999

    for row in analysis["score_ranges"]:
        if row["roi_pct"] > best_roi and row["bets"] >= 20:
            best_roi = row["roi_pct"]
            best_score = row["key"]

    if best_score:
        low = float(best_score.split("-")[0])
        config["min_score"] = low

    # ---------------------------
    # 確率帯
    # ---------------------------
    best_prob = None
    best_roi = -999

    for row in analysis["prob_ranges"]:
        if row["roi_pct"] > best_roi and row["bets"] >= 20:
            best_roi = row["roi_pct"]
            best_prob = row["key"]

    if best_prob:
        if best_prob.endswith("+"):
            config["min_prob"] = float(best_prob.replace("+", ""))

    # ---------------------------
    # 場
    # ---------------------------
    for row in analysis["venues"]:
        if row["roi_pct"] > 100 and row["bets"] >= 30:
            config["allowed_venues"].append(row["key"])

    # ---------------------------
    # 券種
    # ---------------------------
    for row in analysis["bet_types"]:
        if row["roi_pct"] > 100 and row["bets"] >= 30:
            config["allowed_bet_types"].append(row["key"])

    return config
