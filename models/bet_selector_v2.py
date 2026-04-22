# models/bet_selector_v2.py

from models.confidence_v2 import calc_confidence

RACE_SCORE_THRESHOLD = 0.06
TRIFECTA_THRESHOLD = 0.10
TOP1_THRESHOLD = 0.020
GAP_THRESHOLD = 0.003


def select_bets(feature_rows):
    """
    戻り値:
    {
        "adopt": bool,
        "type": "quinella" or "trifecta",
        "bets": [(pattern, prob), ...],
        "confidence": dict
    }
    """

    conf = calc_confidence(feature_rows)

    # 並び替え
    rows = sorted(feature_rows, key=lambda x: x["total_score"], reverse=True)

    # 不採用条件
    if conf["race_score"] < RACE_SCORE_THRESHOLD:
        return {
            "adopt": False,
            "reason": "low_race_score",
            "confidence": conf
        }

    top = rows[0]["lane"]
    second = rows[1]["lane"]
    third = rows[2]["lane"]

    # =========================
    # 3連単発動条件
    # =========================
    if (
        conf["race_score"] >= TRIFECTA_THRESHOLD
        and conf["top1"] >= TOP1_THRESHOLD
        and conf["gap12"] >= GAP_THRESHOLD
    ):
        bets = [
            (f"{top}-{second}-{third}", rows[0]["total_score"]),
            (f"{top}-{second}-{rows[3]['lane']}", rows[1]["total_score"])
        ]

        return {
            "adopt": True,
            "type": "trifecta",
            "bets": bets,
            "confidence": conf
        }

    # =========================
    # 基本:2連単
    # =========================
    bets = [
        (f"{top}-{second}", rows[0]["total_score"]),
        (f"{top}-{third}", rows[1]["total_score"])
    ]

    return {
        "adopt": True,
        "type": "quinella",
        "bets": bets,
        "confidence": conf
    }
