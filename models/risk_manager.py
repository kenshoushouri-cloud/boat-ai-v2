# -*- coding: utf-8 -*-

def judge_race_adoption(context, prediction_result, bets):
    """
    簡易版:
    - オッズ件数が少なすぎる
    - エントリー不足
    - 買い目なし
    - 上位候補の優位性が弱い
    の場合は見送り
    """
    entries = context.get("entries", [])
    odds = context.get("odds", {})
    candidates = prediction_result.get("candidates", [])

    if len(entries) < 6:
        return False, "出走表不足"

    if len(odds) < 3:
        return False, "オッズ不足"

    if not bets:
        return False, "EV基準未達"

    if len(candidates) >= 2:
        top_prob = candidates[0].get("probability", 0)
        second_prob = candidates[1].get("probability", 0)
        if (top_prob - second_prob) < 0.01:
            return False, "上位拮抗"

    return True, None
