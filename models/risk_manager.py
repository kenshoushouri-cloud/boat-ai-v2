# -*- coding: utf-8 -*-

# =========================
# risk_manager v2.1
# =========================
# 方針:
# - EV下限は使わない
# - EVは異常値除外だけに使う
# - v2.1_core 採用ルールに合うレースだけ採用
# - V_06_R3_lane2 は直近不調のため明示除外
# =========================

ADOPTION_RULE_VERSION = "v2.1_core"

# 安全条件
MIN_TOP_PROBABILITY = 0.010
MIN_ODDS = 8.0
MAX_ODDS = 200.0
MAX_EV = 3.0


def _to_int(value, default=None):
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _to_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _ctx_get(context, key, default=None):
    """
    context の構造が多少変わっても拾えるようにする。
    """
    if not isinstance(context, dict):
        return default

    if key in context:
        return context.get(key, default)

    for parent_key in ("race", "race_info", "race_row", "meta", "program"):
        parent = context.get(parent_key)
        if isinstance(parent, dict) and key in parent:
            return parent.get(key, default)

    return default


def _get_top_candidate(prediction_result):
    candidates = prediction_result.get("candidates", []) if isinstance(prediction_result, dict) else []
    if candidates:
        return candidates[0]
    return {}


def _get_top_ticket(prediction_result, bets):
    top = _get_top_candidate(prediction_result)
    ticket = top.get("ticket")
    if ticket:
        return ticket

    if bets:
        return bets[0].get("ticket")

    return None


def _get_first_lane(prediction_result, bets):
    ticket = _get_top_ticket(prediction_result, bets)
    if not ticket:
        return None

    try:
        return int(str(ticket).split("-")[0])
    except Exception:
        return None


def _get_top_probability(prediction_result, bets):
    top = _get_top_candidate(prediction_result)

    prob = top.get("probability")
    if prob is not None:
        return _to_float(prob, 0.0)

    if bets:
        prob = bets[0].get("prob")
        if prob is not None:
            return _to_float(prob, 0.0)

    return 0.0


def _get_title_type(context):
    title_type = _ctx_get(context, "title_type", None)
    if not title_type:
        return "title_unknown"
    return str(title_type)


def _get_race_day_index(context):
    return _to_int(_ctx_get(context, "race_day_index", None), None)


def _get_venue_id(context):
    venue_id = _ctx_get(context, "venue_id", None)
    if venue_id is None:
        return None
    return str(venue_id).zfill(2)


def _get_race_no(context):
    return _to_int(_ctx_get(context, "race_no", None), None)


def _check_bet_safety(bets):
    """
    買い目単位の安全チェック。
    odds / ev が無い買い目は本番採用しない。
    """
    if not bets:
        return False, "買い目なし"

    for bet in bets:
        ticket = bet.get("ticket")

        odds = _to_float(bet.get("odds"), None)
        if odds is None:
            return False, f"odds未取得: {ticket}"

        if odds < MIN_ODDS:
            return False, f"低オッズ除外: {ticket} {odds}"

        if odds > MAX_ODDS:
            return False, f"異常高オッズ除外: {ticket} {odds}"

        ev = _to_float(bet.get("ev"), None)
        if ev is not None and ev > MAX_EV:
            return False, f"異常EV除外: {ticket} EV{ev}"

    return True, None


def _match_v21_rule(context, prediction_result, bets):
    venue_id = _get_venue_id(context)
    race_no = _get_race_no(context)
    title_type = _get_title_type(context)
    race_day_index = _get_race_day_index(context)
    first_lane = _get_first_lane(prediction_result, bets)

    # -------------------------
    # 明示除外ルール
    # V_06_R3_lane2
    # 2026年以降 38走0的中のため除外
    # -------------------------
    if venue_id == "06" and race_no == 3 and first_lane == 2:
        return False, "v2.1除外: V_06_R3_lane2"

    # -------------------------
    # A_grade_mid_lane1
    # grade_title × 中盤 × 1着1号艇
    # -------------------------
    if (
        title_type == "grade_title"
        and race_day_index is not None
        and 2 <= race_day_index <= 4
        and first_lane == 1
    ):
        return True, "A_grade_mid_lane1"

    # -------------------------
    # B_general_day1_lane1
    # general_title × 初日 × 1着1号艇
    # -------------------------
    if (
        title_type == "general_title"
        and race_day_index == 1
        and first_lane == 1
    ):
        return True, "B_general_day1_lane1"

    # -------------------------
    # V_06_R11_lane1
    # 常滑 11R × 1着1号艇
    # -------------------------
    if venue_id == "06" and race_no == 11 and first_lane == 1:
        return True, "V_06_R11_lane1"

    # -------------------------
    # V_18_R10_lane2
    # 下関 10R × 1着2号艇
    # -------------------------
    if venue_id == "18" and race_no == 10 and first_lane == 2:
        return True, "V_18_R10_lane2"

    return False, "v2.1採用条件外"


def judge_race_adoption(context, prediction_result, bets):
    """
    morning_summary_job から呼ばれる採用判定。
    return: (adopt: bool, reason: str)
    """
    race_id = None
    if isinstance(context, dict):
        race_id = context.get("race_id") or _ctx_get(context, "race_id", None)

    if not bets:
        return False, "買い目なし"

    top_probability = _get_top_probability(prediction_result, bets)
    if top_probability < MIN_TOP_PROBABILITY:
        return False, f"top確率不足: {top_probability:.4f}"

    safe_ok, safe_reason = _check_bet_safety(bets)
    if not safe_ok:
        return False, safe_reason

    rule_ok, rule_name = _match_v21_rule(context, prediction_result, bets)
    if not rule_ok:
        return False, rule_name

    print(f"adopt v2.1: {race_id} rule={rule_name}")
    return True, rule_name