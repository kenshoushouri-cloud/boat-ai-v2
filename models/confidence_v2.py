# -*- coding: utf-8 -*-


def calc_confidence(prediction_result):
    """
    prediction_result: predict_race() の戻り値
    戻り値: confidence dict
    """
    candidates = prediction_result.get("candidates", [])
    exacta_candidates = prediction_result.get("exacta_candidates", [])

    if not candidates:
        return {
            "race_score": 0.0,
            "top1_prob": 0.0,
            "top2_prob": 0.0,
            "gap12": 0.0,
            "exacta_top1_prob": 0.0,
            "exacta_gap12": 0.0,
            "top1_ev": None,
            "top1_odds": None,
        }

    tri_top1 = candidates[0]["probability"] if len(candidates) >= 1 else 0.0
    tri_top2 = candidates[1]["probability"] if len(candidates) >= 2 else 0.0
    ex_top1 = exacta_candidates[0]["probability"] if len(exacta_candidates) >= 1 else 0.0
    ex_top2 = exacta_candidates[1]["probability"] if len(exacta_candidates) >= 2 else 0.0

    gap12_tri = tri_top1 - tri_top2
    gap12_ex = ex_top1 - ex_top2

    # race_score: 1位の支配力を表す総合スコア
    race_score = (
        (ex_top1 * 1.8)
        + (tri_top1 * 0.8)
        + (gap12_ex * 3.0)
        + (gap12_tri * 2.0)
    )

    top1_ev = candidates[0].get("ev")
    top1_odds = candidates[0].get("odds")

    return {
        "race_score": round(race_score, 6),
        "top1_prob": round(tri_top1, 6),
        "top2_prob": round(tri_top2, 6),
        "gap12": round(gap12_tri, 6),
        "exacta_top1_prob": round(ex_top1, 6),
        "exacta_gap12": round(gap12_ex, 6),
        "top1_ev": round(top1_ev, 3) if top1_ev is not None else None,
        "top1_odds": top1_odds,
    }