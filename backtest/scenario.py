# -*- coding: utf-8 -*-

def detect_scenario_type(context, prediction_result):
    entries = context.get("entries", [])
    candidates = prediction_result.get("candidates", [])

    if len(entries) < 6:
        return "unknown"

    if len(candidates) < 2:
        return "unknown"

    top1_ticket = candidates[0].get("ticket", "")
    top2_ticket = candidates[1].get("ticket", "")
    top1_prob = candidates[0].get("probability", 0) or 0
    top2_prob = candidates[1].get("probability", 0) or 0
    prob_gap = top1_prob - top2_prob

    if not top1_ticket or not top2_ticket:
        return "unknown"

    first1 = top1_ticket.split("-")[0]
    first2 = top2_ticket.split("-")[0]

    # 強いイン逃げだけ escape とする
    if first1 == "1" and first2 == "1" and top1_prob >= 0.15 and prob_gap >= 0.02:
        return "escape"

    # 2〜3コース主導は attack
    if first1 in {"2", "3"}:
        return "attack"

    # 4〜6頭は穴寄り
    if first1 in {"4", "5", "6"}:
        return "hole"

    return "mixed"
