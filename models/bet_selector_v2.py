# -*- coding: utf-8 -*-
from models.confidence_v2 import calc_confidence

# ============================================================
# パラメータ（バックテストで調整）
# ============================================================

# レーススコア足切り（低すぎるレースは見送り）
RACE_SCORE_MIN = 0.08

# EV（期待値）足切り: EV >= 1.0 で期待値プラス
EV_MIN = 0.90

# 最低オッズ: これ以下はトリガミリスクがある
ODDS_MIN = 5.0

# 1レース最大買い目数
MAX_BETS = 5

# 上位候補のスコア差閾値（1位と2位が接近しすぎていれば見送り）
GAP_MIN = 0.002


def select_bets(prediction_result, min_ev=EV_MIN, min_odds=ODDS_MIN, max_bets=MAX_BETS):
    """
    prediction_result: predict_race() の戻り値

    戻り値: list of {
        ticket, prob, odds, ev
    }
    空リスト = 見送り
    """
    candidates = prediction_result.get("candidates", [])
    race_score = prediction_result.get("race_score", 0.0)

    if not candidates:
        return []

    conf = calc_confidence(prediction_result)

    # レーススコア足切り
    if conf["race_score"] < RACE_SCORE_MIN:
        print(f"  SKIP: race_score低 {conf['race_score']:.4f} < {RACE_SCORE_MIN}")
        return []

    # 1位と2位の差が小さすぎる場合は見送り（混戦）
    if conf["gap12"] < GAP_MIN:
        print(f"  SKIP: gap12小 {conf['gap12']:.4f} < {GAP_MIN}")
        return []

    # EV・オッズ条件を満たす買い目を抽出
    bets = []
    for c in candidates:
        odds = c.get("odds")
        ev = c.get("ev")
        prob = c.get("probability", 0.0)

        if odds is None or ev is None:
            continue
        if odds < min_odds:
            continue
        if ev < min_ev:
            continue

        bets.append({
            "ticket": c["ticket"],
            "prob": prob,
            "odds": odds,
            "ev": ev,
        })

        if len(bets) >= max_bets:
            break

    if not bets:
        print(f"  SKIP: EV/オッズ条件を満たす買い目なし")
        return []

    # EVの高い順にソート
    bets.sort(key=lambda x: x["ev"], reverse=True)

    return bets