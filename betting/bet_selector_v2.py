# -*- coding: utf-8 -*-

def select_bets(prediction_result, min_ev=1.12, min_odds=4.5, max_bets=3):
    candidates = prediction_result.get("candidates", [])
    if not candidates:
        return []

    bets = []
    for c in candidates:
        odds = c.get("odds")
        prob = c.get("probability", 0)

        if odds is None:
            continue

        ev = prob * float(odds)
        if ev < min_ev:
            continue
        if float(odds) < min_odds:
            continue

        bets.append({
            "ticket": c["ticket"],
            "prob": round(prob, 6),
            "odds": float(odds),
            "ev": round(ev, 3)
        })

    bets.sort(key=lambda x: (x["ev"], x["prob"]), reverse=True)
    return bets[:max_bets]
