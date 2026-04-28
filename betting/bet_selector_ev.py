# -*- coding: utf-8 -*-

# =========================
# 直前配信用: EV・オッズ基準セレクター
# オッズ確定後に使用する
# =========================

# EV（期待値）基準: EV >= 1.0 で期待値プラス
EV_MIN = 0.90

# 最低オッズ: これ以下はトリガミリスクが高い
ODDS_MIN = 5.0

# 最大買い目数
MAX_BETS = 3


def select_bets_ev(prediction_result, min_ev=EV_MIN, min_odds=ODDS_MIN, max_bets=MAX_BETS):
    """
    オッズ確定後のEV基準買い目選択。
    pre_race_job で使用する。

    戻り値: list of {ticket, prob, odds, ev}
    空リスト = 見送り
    """
    candidates = prediction_result.get("candidates", [])

    if not candidates:
        print("  EV selector: 候補なし")
        return []

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
            "bet_type": "trifecta",
        })

        if len(bets) >= max_bets:
            break

    if not bets:
        print(f"  EV selector: 条件未達 (EV>={min_ev} オッズ>={min_odds})")
        return []

    # EVの高い順にソート
    bets.sort(key=lambda x: x["ev"], reverse=True)
    return bets