# -*- coding: utf-8 -*-

# =========================
# 方針
# - 本線は3連単
# - ただし低配当っぽい3連単は買わない
# - 異常高オッズ・低確率EV暴れを除外する
# - 3連単条件に届かない時だけ2連単を使う
# - 2連単も保険なので厳しめ
# - betsには odds / ev も引き継ぐ
# =========================

# -------------------------
# 3連単条件
# -------------------------
TRIFECTA_RACE_SCORE_THRESHOLD = 0.20
TRIFECTA_EXACTA_TOP1_THRESHOLD = 0.060

# 高すぎる確率 = 本命すぎる = 低配当リスク
TRIFECTA_PROB_MAX = 0.030

# 低すぎる確率 = オッズだけでEVが跳ねやすい
TRIFECTA_PROB_MIN = 0.010

# オッズ安全帯
TRIFECTA_ODDS_MIN = 8.0
TRIFECTA_ODDS_MAX = 200.0

# EVが大きすぎる場合は、低確率×超高オッズの暴れとみなす
TRIFECTA_EV_MAX = 3.0

TRIFECTA_BET_MAX = 2

# -------------------------
# 2連単条件(保険)
# -------------------------
EXACTA_TOP1_MIN = 0.060
EXACTA_TOP12_SUM_MIN = 0.115
EXACTA_GAP_MIN = 0.005
EXACTA_TOP1_MAX = 0.090
EXACTA_TOP2_MAX = 0.065
EXACTA_TRI_TOP1_MIN = 0.018
EXACTA_BET_MAX = 2


def _to_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _extract_odds(row):
    """
    candidate側のキー名揺れに対応して odds を取得する。
    """
    for key in ["odds", "trifecta_odds", "exacta_odds", "odds_value"]:
        if key in row and row.get(key) is not None:
            return _to_float(row.get(key))
    return None


def _extract_ev(row, prob=None, odds=None):
    """
    ev / expected_value があれば使う。
    なければ prob * odds で計算する。
    """
    ev = row.get("ev", row.get("expected_value"))
    ev = _to_float(ev)

    if ev is None and prob is not None and odds is not None:
        ev = round(prob * odds, 4)

    return ev


def _make_bet(row, bet_type):
    """
    prediction候補から保存用betを作る。
    probability / odds / ev をここで必ず引き継ぐ。
    """
    prob = _to_float(row.get("probability", row.get("prob", 0.0)), 0.0)
    odds = _extract_odds(row)
    ev = _extract_ev(row, prob=prob, odds=odds)

    bet = {
        "ticket": row["ticket"],
        "prob": prob,
        "bet_type": bet_type,
    }

    if odds is not None:
        bet["odds"] = odds

    if ev is not None:
        bet["ev"] = ev

    return bet


def _passes_trifecta_bet_safety(row):
    """
    3連単の個別買い目安全フィルター。
    低確率×超高オッズによるEV暴れを避ける。
    """
    ticket = row.get("ticket")
    prob = _to_float(row.get("probability", row.get("prob", 0.0)), 0.0)
    odds = _extract_odds(row)
    ev = _extract_ev(row, prob=prob, odds=odds)

    if prob < TRIFECTA_PROB_MIN:
        return False, f"{ticket} 確率下限未満 prob={prob:.4f}"

    if odds is None:
        return False, f"{ticket} オッズなし"

    if odds < TRIFECTA_ODDS_MIN:
        return False, f"{ticket} オッズ低すぎ odds={odds:.1f}"

    if odds > TRIFECTA_ODDS_MAX:
        return False, f"{ticket} オッズ高すぎ odds={odds:.1f}"

    if ev is not None and ev > TRIFECTA_EV_MAX:
        return False, f"{ticket} EV高すぎ ev={ev:.3f}"

    return True, None


def _safe_trifecta_candidates(prediction_result):
    """
    3連単候補から安全フィルターを通過したものだけを返す。
    """
    candidates = prediction_result.get("candidates", [])
    safe = []

    for c in candidates:
        ok, reason = _passes_trifecta_bet_safety(c)
        if ok:
            safe.append(c)
        else:
            # ログが多すぎないよう、候補上位だけ理由を出す
            if len(safe) < 2:
                print("bet_selector trifecta safety skip:", reason)

    return safe


def _build_trifecta_bets(prediction_result, max_bets=2):
    candidates = _safe_trifecta_candidates(prediction_result)
    if not candidates:
        return []

    bets = []

    top = candidates[0]
    bets.append(_make_bet(top, "trifecta"))

    if max_bets <= 1:
        return bets

    top_first, top_second, top_third = top["ticket"].split("-")
    second_choice = None

    # 1着同じ・2着同じ・3着違い
    for c in candidates[1:]:
        first, second, third = c["ticket"].split("-")
        if first == top_first and second == top_second and third != top_third:
            second_choice = _make_bet(c, "trifecta")
            break

    # 1着同じ・2着違い
    if second_choice is None:
        for c in candidates[1:]:
            first, second, third = c["ticket"].split("-")
            if first == top_first and second != top_second:
                second_choice = _make_bet(c, "trifecta")
                break

    if second_choice:
        bets.append(second_choice)

    return bets[:max_bets]


def _build_exacta_bets(prediction_result, max_bets=2):
    exacta_candidates = prediction_result.get("exacta_candidates", [])
    if not exacta_candidates:
        return []

    bets = []
    for row in exacta_candidates[:max_bets]:
        bets.append(_make_bet(row, "exacta"))

    return bets


def _passes_trifecta_filter(prediction_result):
    race_score = prediction_result.get("race_score", 0.0)
    candidates = prediction_result.get("candidates", [])
    exacta_candidates = prediction_result.get("exacta_candidates", [])

    if not candidates:
        return False, "3連単候補不足"

    if not exacta_candidates:
        return False, "2連単候補不足"

    tri_top1 = candidates[0].get("probability", 0.0)
    exacta_top1 = exacta_candidates[0].get("probability", 0.0)

    if race_score < TRIFECTA_RACE_SCORE_THRESHOLD:
        return False, "3連単score不足"

    if exacta_top1 < TRIFECTA_EXACTA_TOP1_THRESHOLD:
        return False, "3連単軸不足"

    # 本命すぎる3連単は、実質的に旨味が薄いので切る
    if tri_top1 > TRIFECTA_PROB_MAX:
        return False, "3連単低配当リスク"

    safe_candidates = _safe_trifecta_candidates(prediction_result)
    if not safe_candidates:
        return False, "3連単安全条件不足"

    return True, None


def _passes_exacta_filter(prediction_result):
    exacta_candidates = prediction_result.get("exacta_candidates", [])
    trifecta_candidates = prediction_result.get("candidates", [])

    if len(exacta_candidates) < 2:
        return False, "2連単候補不足"

    top1 = exacta_candidates[0].get("probability", 0.0)
    top2 = exacta_candidates[1].get("probability", 0.0)
    top12_sum = top1 + top2
    gap = top1 - top2

    tri_top1 = trifecta_candidates[0].get("probability", 0.0) if trifecta_candidates else 0.0

    if top1 < EXACTA_TOP1_MIN:
        return False, "2連単軸弱い"

    if top12_sum < EXACTA_TOP12_SUM_MIN:
        return False, "2連単上位弱い"

    if gap < EXACTA_GAP_MIN:
        return False, "2連単上位拮抗"

    if top1 > EXACTA_TOP1_MAX:
        return False, "2連単低配当リスク"

    if top2 > EXACTA_TOP2_MAX:
        return False, "2連単2位強すぎ"

    if tri_top1 < EXACTA_TRI_TOP1_MIN:
        return False, "3連単妙味不足"

    return True, None


def select_bets(prediction_result, max_bets=2):
    # =========================
    # まず3連単を優先
    # =========================
    ok_tri, reason_tri = _passes_trifecta_filter(prediction_result)
    if ok_tri:
        bets = _build_trifecta_bets(
            prediction_result,
            max_bets=min(max_bets, TRIFECTA_BET_MAX)
        )
        if bets:
            return bets
    else:
        print("bet_selector trifecta skip:", reason_tri)

    # =========================
    # 次に2連単を保険で使う
    # =========================
    ok_ex, reason_ex = _passes_exacta_filter(prediction_result)
    if not ok_ex:
        print("bet_selector exacta skip:", reason_ex)
        return []

    return _build_exacta_bets(
        prediction_result,
        max_bets=min(max_bets, EXACTA_BET_MAX)
    )