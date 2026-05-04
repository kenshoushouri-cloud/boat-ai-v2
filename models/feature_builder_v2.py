# -*- coding: utf-8 -*-

# ============================================================
# NULLデータの平均値補完
# ============================================================
DEFAULT_NATIONAL_PLACE2 = 32.0
DEFAULT_LOCAL_PLACE2 = 30.0
DEFAULT_MOTOR_PLACE2 = 33.0
DEFAULT_BOAT_PLACE2 = 34.0
DEFAULT_AVG_ST = 0.18

# ============================================================
# 会場×コース別 1着率補正スコア
# 実データ（2025-03-13〜2026-04-30）から計算
# ============================================================
VENUE_LANE_SCORES = {
    "01": {  # 桐生: 外コース強い・荒れやすい
        1: 2.762, 2: 2.747, 3: 3.385, 4: 4.070, 5: 3.537, 6: 2.343,
    },
    "06": {  # 常滑: 2〜3コース差しが効く
        1: 2.932, 2: 3.401, 3: 3.571, 4: 3.195, 5: 2.694, 6: 2.403,
    },
    "12": {  # 住之江: ほぼ平均・1コースやや強い
        1: 3.249, 2: 3.344, 3: 2.957, 4: 2.824, 5: 2.313, 6: 1.553,
    },
    "18": {  # 下関: 1コース強い・5〜6コース極端に弱い
        1: 3.509, 2: 3.116, 3: 2.908, 4: 2.648, 5: 1.380, 6: 1.355,
    },
    "24": {  # 大村: 1コース最強・外コース弱い
        1: 3.561, 2: 2.880, 3: 2.659, 4: 2.267, 5: 2.049, 6: 1.314,
    },
}

DEFAULT_LANE_SCORES = {1: 3.2, 2: 3.1, 3: 3.1, 4: 3.0, 5: 2.4, 6: 1.8}

# ============================================================
# レース番号別×コース補正値
# R11・R12は1コース圧倒的、R2・R3は外コース比較的強い
# ============================================================
RACE_NO_LANE_BIAS = {
    1:  {1: 0.988, 2: 0.947, 3: 1.163, 4: 1.008, 5: 1.279, 6: 0.667},
    2:  {1: 0.808, 2: 1.374, 3: 1.188, 4: 1.316, 5: 1.097, 6: 1.036},
    3:  {1: 0.838, 2: 1.229, 3: 1.313, 4: 1.005, 5: 1.114, 6: 1.617},
    4:  {1: 0.935, 2: 1.046, 3: 1.022, 4: 1.216, 5: 1.098, 6: 1.098},
    5:  {1: 0.964, 2: 1.144, 3: 0.862, 4: 1.004, 5: 1.204, 6: 1.250},
    6:  {1: 0.936, 2: 1.018, 3: 1.023, 4: 1.272, 5: 0.870, 6: 1.404},
    7:  {1: 0.988, 2: 1.019, 3: 1.256, 4: 0.784, 5: 0.870, 6: 1.008},
    8:  {1: 0.988, 2: 0.780, 3: 0.987, 4: 1.218, 5: 1.359, 6: 0.794},
    9:  {1: 1.009, 2: 1.069, 3: 0.981, 4: 0.988, 5: 0.795, 6: 0.978},
    10: {1: 1.049, 2: 0.963, 3: 0.966, 4: 0.830, 5: 0.993, 6: 0.825},
    11: {1: 1.205, 2: 0.697, 3: 0.698, 4: 0.822, 5: 0.780, 6: 0.642},
    12: {1: 1.280, 2: 0.684, 3: 0.634, 4: 0.565, 5: 0.736, 6: 0.500},
}

# ============================================================
# 選手級別×コース補正値
# A1選手が外コースにいると平均の2倍強い
# ============================================================
CLASS_LANE_BIAS = {
    1: {1: 1.268, 2: 1.141, 3: 0.724, 4: 0.713},  # 1コース
    2: {1: 1.303, 2: 1.186, 3: 0.802, 4: 1.204},  # 2コース
    3: {1: 1.401, 2: 1.115, 3: 0.796, 4: 1.151},  # 3コース
    4: {1: 1.777, 2: 1.187, 3: 0.733, 4: 0.500},  # 4コース
    5: {1: 1.976, 2: 1.310, 3: 0.623, 4: 0.660},  # 5コース
    6: {1: 2.000, 2: 1.139, 3: 0.500, 4: 0.500},  # 6コース
}

# 会場別外コース補正乗数
VENUE_OUTER_MULTIPLIER = {
    "01": 1.4, "06": 1.2, "12": 0.9, "18": 0.7, "24": 0.6,
}


def _to_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _to_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _lane_score(lane, venue_id):
    """会場×コース別1着率から算出したスコア"""
    lane = _to_int(lane)
    scores = VENUE_LANE_SCORES.get(str(venue_id).zfill(2), DEFAULT_LANE_SCORES)
    return scores.get(lane, 0.0)


def _race_no_bias(lane, race_no):
    """レース番号別コース補正"""
    lane = _to_int(lane)
    race_no = _to_int(race_no)
    bias = RACE_NO_LANE_BIAS.get(race_no, {})
    return bias.get(lane, 1.0)


def _class_lane_bias(lane, racer_class):
    """選手級別×コース補正"""
    lane = _to_int(lane)
    racer_class = _to_int(racer_class)
    if racer_class == 0:
        return 1.0
    bias = CLASS_LANE_BIAS.get(lane, {})
    return bias.get(racer_class, 1.0)


def _class_score(c):
    return {1: 4.5, 2: 3.0, 3: 1.6, 4: 0.6}.get(_to_int(c), 0.5)


def _st_score(st):
    if st is None or st == "":
        return 0.0
    st = _to_float(st, DEFAULT_AVG_ST)
    return max(0.0, (0.18 - st) * 46.0)


def _two_rate_score(nat, loc):
    nat = _to_float(nat, DEFAULT_NATIONAL_PLACE2) if nat is not None else DEFAULT_NATIONAL_PLACE2
    loc = _to_float(loc, DEFAULT_LOCAL_PLACE2) if loc is not None else DEFAULT_LOCAL_PLACE2
    return (nat * 0.55 + loc * 0.45) / 7.2


def _motor_score(m):
    val = _to_float(m, DEFAULT_MOTOR_PLACE2) if m is not None else DEFAULT_MOTOR_PLACE2
    return val / 38.0


def _boat_score(b):
    val = _to_float(b, DEFAULT_BOAT_PLACE2) if b is not None else DEFAULT_BOAT_PLACE2
    return val / 42.0


def _penalty(f, l):
    return _to_int(f) * 1.5 + _to_int(l) * 0.3


def _build_rank_map(ex_map):
    pairs = []
    for k, v in ex_map.items():
        if v.get("exhibition_time") is not None:
            pairs.append((int(k), _to_float(v["exhibition_time"])))
    pairs.sort(key=lambda x: x[1])
    rank = {}
    for i, (lane, _) in enumerate(pairs, 1):
        rank[lane] = i
    return rank


def _ex_score(ex, rank_map):
    if not ex:
        return 0.0
    lane = _to_int(ex.get("lane"))
    ex_time = ex.get("exhibition_time")
    if ex_time is None:
        return 0.0
    ex_time = _to_float(ex_time)
    rank = rank_map.get(lane)
    score = 0.0
    if ex_time <= 6.55:
        score += 3.2
    elif ex_time <= 6.60:
        score += 2.7
    elif ex_time <= 6.65:
        score += 2.2
    elif ex_time <= 6.70:
        score += 1.4
    elif ex_time <= 6.75:
        score += 0.5
    if rank == 1:
        score += 2.0
    elif rank == 2:
        score += 1.4
    elif rank == 3:
        score += 0.8
    elif rank == 4:
        score += 0.2
    elif rank == 6:
        score -= 0.8
    return score


def _tilt_score(ex):
    if not ex:
        return 0.0
    tilt = ex.get("tilt")
    if tilt is None:
        return 0.0
    tilt = _to_float(tilt, 0.0)
    if tilt >= 3.0:
        return 0.8
    if tilt >= 2.0:
        return 0.5
    if tilt >= 1.0:
        return 0.2
    if tilt <= -0.5:
        return -0.1
    return 0.0


def _start_timing_score(ex):
    if not ex:
        return 0.0
    st = ex.get("start_timing")
    if st is None:
        return 0.0
    st = _to_float(st, 0.30)
    if st <= 0.10:
        return 1.2
    if st <= 0.12:
        return 0.9
    if st <= 0.14:
        return 0.6
    if st <= 0.16:
        return 0.3
    if st >= 0.22:
        return -0.3
    return 0.0


def _outside_attack(lane, avg_st, ex, venue_id):
    lane = _to_int(lane)
    st = _to_float(avg_st, DEFAULT_AVG_ST) if avg_st is not None else DEFAULT_AVG_ST
    outer_multiplier = VENUE_OUTER_MULTIPLIER.get(str(venue_id).zfill(2), 1.0)
    score = 0.0
    if lane in (3, 4, 5):
        if st <= 0.14:
            score += 1.2
        elif st <= 0.15:
            score += 0.8
        elif st <= 0.16:
            score += 0.4
    if ex and ex.get("exhibition_time") is not None:
        ex_time = _to_float(ex["exhibition_time"])
        if lane in (3, 4, 5) and ex_time <= 6.65:
            score += 1.2
        elif lane in (3, 4, 5) and ex_time <= 6.70:
            score += 0.6
    return score * outer_multiplier


def _third_bias(lane, avg_st, nat, loc, ex, venue_id):
    lane = _to_int(lane)
    st = _to_float(avg_st, DEFAULT_AVG_ST) if avg_st is not None else DEFAULT_AVG_ST
    nat = _to_float(nat, DEFAULT_NATIONAL_PLACE2) if nat is not None else DEFAULT_NATIONAL_PLACE2
    loc = _to_float(loc, DEFAULT_LOCAL_PLACE2) if loc is not None else DEFAULT_LOCAL_PLACE2
    mix = nat * 0.55 + loc * 0.45
    outer_multiplier = VENUE_OUTER_MULTIPLIER.get(str(venue_id).zfill(2), 1.0)
    score = 0.0
    if lane == 2:
        score += 0.10
    elif lane == 3:
        score += 0.85
    elif lane == 4:
        score += 1.10
    elif lane == 5:
        score += 1.00
    elif lane == 6:
        score += 0.55
    if st <= 0.15:
        score += 0.25
    if mix >= 40:
        score += 0.35
    elif mix >= 30:
        score += 0.20
    if ex and ex.get("exhibition_time") is not None:
        ex_time = _to_float(ex["exhibition_time"])
        if lane in (3, 4, 5, 6) and ex_time <= 6.65:
            score += 0.9
        elif lane in (3, 4, 5, 6) and ex_time <= 6.70:
            score += 0.4
    if lane in (4, 5, 6):
        score *= outer_multiplier
    return score


def build_entry_features(context):
    entries = context.get("entries", [])
    ex_map = context.get("exhibition", {}) or {}
    venue_id = str(context.get("venue_id", "")).zfill(2)
    race_no = _to_int(context.get("race_no", 0))
    rank_map = _build_rank_map(ex_map)

    rows = []

    for e in entries:
        lane = _to_int(e.get("lane"))
        ex = ex_map.get(str(lane), {})
        racer_class = _to_int(e.get("racer_class", 0))

        nat2 = e.get("national_place2_rate") or e.get("national_2rate")
        loc2 = e.get("local_place2_rate") or e.get("local_2rate")
        avg_st = e.get("avg_st") or e.get("average_st") or e.get("national_avg_st")
        motor2 = e.get("motor_place2_rate") or e.get("motor_2rate")
        boat2 = e.get("boat_place2_rate") or e.get("boat_2rate")

        # ベーススコア（会場×コース補正済み）
        base = _lane_score(lane, venue_id)

        # レース番号補正を乗算
        race_bias = _race_no_bias(lane, race_no)

        # 選手級別×コース補正を乗算
        class_bias = _class_lane_bias(lane, racer_class)

        # コアスコア（補正乗算）
        core_score = base * race_bias * class_bias

        # 加算スコア
        additive_score = (
            _class_score(racer_class)
            + _st_score(avg_st)
            + _two_rate_score(nat2, loc2)
            + _motor_score(motor2)
            + _boat_score(boat2)
            + _outside_attack(lane, avg_st, ex, venue_id)
            + _third_bias(lane, avg_st, nat2, loc2, ex, venue_id)
            + _ex_score(ex, rank_map)
            + _tilt_score(ex)
            + _start_timing_score(ex)
            - _penalty(e.get("f_count"), e.get("l_count"))
        )

        score = core_score + additive_score

        rows.append({
            "lane": lane,
            "score": round(score, 4),
            "race_bias": round(race_bias, 3),
            "class_bias": round(class_bias, 3),
        })

    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows