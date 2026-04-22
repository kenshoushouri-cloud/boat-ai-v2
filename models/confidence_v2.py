# models/confidence_v2.py

def calc_confidence(feature_rows):
    """
    feature_rows: [{lane, total_score}, ...]
    """
    scores = sorted(
        [float(r.get("total_score", 0)) for r in feature_rows],
        reverse=True
    )

    if len(scores) < 3:
        return {
            "race_score": 0,
            "top1": 0,
            "top2": 0,
            "gap12": 0,
            "bet_prob_sum": 0
        }

    top1 = scores[0]
    top2 = scores[1]
    top3 = scores[2]

    race_score = top1 + top2
    gap12 = top1 - top2
    gap23 = top2 - top3

    bet_prob_sum = top1 + top2

    return {
        "race_score": race_score,
        "top1": top1,
        "top2": top2,
        "gap12": gap12,
        "gap23": gap23,
        "bet_prob_sum": bet_prob_sum
    }
