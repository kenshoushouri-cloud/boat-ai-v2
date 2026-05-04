# -*- coding: utf-8 -*-
"""
直前配信用・バックテスト共通 EVセレクター

目的:
- 本番の直前配信とバックテストの最終買い目選定を統一する
- stable / ana でEV・オッズ・点数条件を分ける
- 3連単専用
"""

# ============================================================
# モード別ルール
# ============================================================

MODE_RULES = {
    "stable": {
        "label": "安定モード",
        "min_ev": 1.10,
        "min_odds": 3.5,
        "max_odds": 25.0,
        "min_prob": 0.015,
        "max_bets": 2,

        # 安定モードは同じ1着軸の2点まで
        "same_first_only": True,
    },
    "ana": {
        "label": "馬王モード",
        "min_ev": 1.35,
        "min_odds": 12.0,
        "max_odds": 80.0,
        "min_prob": 0.008,
        "max_bets": 1,

        # 穴は1点勝負
        "same_first_only": False,
    },
}


# ============================================================
# utility
# ============================================================

def _to_float(v, default=None):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _candidate_prob(c):
    return _to_float(c.get("probability", c.get("prob", 0.0)), 0.0)


def _candidate_odds(c):
    return _to_float(c.get("odds"), None)


def _candidate_ev(c):
    ev = _to_float(c.get("ev"), None)
    if ev is not None:
        return ev

    prob = _candidate_prob(c)
    odds = _candidate_odds(c)

    if odds is None:
        return None

    return prob * odds


def _normalize_candidate(c):
    ticket = c.get("ticket")
    if not ticket:
        return None

    prob = _candidate_prob(c)
    odds = _candidate_odds(c)
    ev = _candidate_ev(c)

    if odds is None or ev is None:
        return None

    return {
        "ticket": ticket,
        "prob": prob,
        "odds": odds,
        "ev": ev,
        "bet_type": "trifecta",
    }


# ============================================================
# core selector
# ============================================================

def _select_by_rule(prediction_result, rule):
    candidates = prediction_result.get("candidates", [])

    if not candidates:
        return [], "候補なし"

    filtered = []

    for c in candidates:
        row = _normalize_candidate(c)
        if not row:
            continue

        if row["odds"] < rule["min_odds"]:
            continue

        if row["odds"] > rule["max_odds"]:
            continue

        if row["prob"] < rule["min_prob"]:
            continue

        if row["ev"] < rule["min_ev"]:
            continue

        filtered.append(row)

    if not filtered:
        return [], (
            f"EV条件未達 "
            f"EV>={rule['min_ev']} "
            f"odds={rule['min_odds']}〜{rule['max_odds']} "
            f"prob>={rule['min_prob']}"
        )

    # EV優先、同EVなら確率優先
    filtered.sort(
        key=lambda x: (x["ev"], x["prob"], x["odds"]),
        reverse=True
    )

    max_bets = int(rule.get("max_bets", 1))
    same_first_only = bool(rule.get("same_first_only", False))

    if max_bets <= 1:
        return filtered[:1], None

    top = filtered[0]
    bets = [top]

    if same_first_only:
        top_first = top["ticket"].split("-")[0]

        for c in filtered[1:]:
            first = c["ticket"].split("-")[0]

            # 同じ1着軸の別買い目だけ追加
            if first == top_first and c["ticket"] != top["ticket"]:
                bets.append(c)
                break
    else:
        for c in filtered[1:]:
            if c["ticket"] != top["ticket"]:
                bets.append(c)

            if len(bets) >= max_bets:
                break

    return bets[:max_bets], None


# ============================================================
# public functions
# ============================================================

def select_bets_ev_mode(prediction_result, mode="stable", override_rule=None):
    """
    stable / ana モード対応のEVセレクター。

    戻り値:
        bets, reason

    bets:
        [
            {
                "ticket": "1-2-3",
                "prob": 0.023,
                "odds": 12.5,
                "ev": 1.42,
                "bet_type": "trifecta",
            }
        ]

    reason:
        見送り理由。採用時は None。
    """
    rule = dict(MODE_RULES.get(mode, MODE_RULES["stable"]))

    if override_rule:
        rule.update(override_rule)

    return _select_by_rule(prediction_result, rule)


def select_bets_ev(
    prediction_result,
    min_ev=1.10,
    min_odds=3.5,
    max_bets=2,
    max_odds=80.0,
    min_prob=0.0,
):
    """
    旧 pre_race_job 互換用。
    既存コードが select_bets_ev() を呼んでいても動くように残す。

    戻り値:
        bets のみ
    """
    rule = {
        "min_ev": min_ev,
        "min_odds": min_odds,
        "max_odds": max_odds,
        "min_prob": min_prob,
        "max_bets": max_bets,
        "same_first_only": True,
    }

    bets, reason = _select_by_rule(prediction_result, rule)

    if not bets:
        print(f"  EV selector: {reason}")
        return []

    return bets