# -*- coding: utf-8 -*-

# =========================
# 方針
# - 本線は3連単
# - ただし低配当っぽい3連単は買わない
# - 3連単条件に届かない時だけ2連単を使う
# - 2連単も保険なので厳しめ
# =========================

# -------------------------
# 3連単条件
# -------------------------
TRIFECTA_RACE_SCORE_THRESHOLD = 0.20
TRIFECTA_EXACTA_TOP1_THRESHOLD = 0.060
TRIFECTA_PROB_MAX = 0.030      # 高すぎる=本命すぎる=低配当リスク
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


def _build_trifecta_bets(prediction_result, max_bets=2):
    candidates = prediction_result.get("candidates", [])
    if not candidates:
        return []

    bets = []

    top = candidates[0]
    bets.append({
        "ticket": top["ticket"],
        "prob": top.get("probability", 0.0),
        "bet_type": "trifecta",
    })

    if max_bets <= 1:
        return bets

    top_first, top_second, top_third = top["ticket"].split("-")
    second_choice = None

    # 1着同じ・2着同じ・3着違い
    for c in candidates[1:]:
        first, second, third = c["ticket"].split("-")
        if first == top_first and second == top_second and third != top_third:
            second_choice = {
                "ticket": c["ticket"],
                "prob": c.get("probability", 0.0),
                "bet_type": "trifecta",
            }
            break

    # 1着同じ・2着違い
    if second_choice is None:
        for c in candidates[1:]:
            first, second, third = c["ticket"].split("-")
            if first == top_first and second != top_second:
                second_choice = {
                    "ticket": c["ticket"],
                    "prob": c.get("probability", 0.0),
                    "bet_type": "trifecta",
                }
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
        bets.append({
            "ticket": row["ticket"],
            "prob": row.get("probability", 0.0),
            "bet_type": "exacta",
        })

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

    # 本命すぎる3連単は、実質的に旨味が薄いので切る
    if tri_top1 > TRIFECTA_PROB_MAX:
        return False, "3連単低配当リスク"

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
        return False, "2連単2位強すぎ"

    if tri_top1 < EXACTA_TRI_TOP1_MIN:
        return False, "3連単妙味不足"

    return True, None


def select_bets(prediction_result, max_bets=2):
    # =========================
    # まず3連単を優先
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
    # 次に2連単を保険で使う
    # =========================
    ok_ex, reason_ex = _passes_exacta_filter(prediction_result)
    if not ok_ex:
        print("bet_selector exacta skip:", reason_ex)
        return []

    return _build_exacta_bets(
        prediction_result,
        max_bets=min(max_bets, EXACTA_BET_MAX)
    )
