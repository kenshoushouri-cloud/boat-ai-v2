# -*- coding: utf-8 -*-

def judge_race_adoption(context, prediction_result, bets):
    entries = context.get("entries", []) or []
    candidates = prediction_result.get("candidates", []) or []

    if len(entries) < 6:
        return False, "出走表不足"

    if len(candidates) < 3:
        return False, "候補不足"

    if not bets:
        return False, "買い目なし"

    top1 = candidates[0].get("probability", 0.0)
    top2 = candidates[1].get("probability", 0.0)
    bet_prob_sum = sum(b.get("prob", 0.0) for b in bets)

    # 本当に壊れている時だけ止める
    if top1 < 0.010:
        return False, "軸不在"

    if (top1 + top2) < 0.022:
        return False, "上位弱い"

    if bet_prob_sum < 0.018:
        return False, "買い目弱い"

    return True, None
