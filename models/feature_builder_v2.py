# -*- coding: utf-8 -*-

# ============================================================
# NULLデータの平均値補完
# データが溜まったらバックテストで調整する
# ============================================================
DEFAULT_NATIONAL_PLACE2 = 32.0   # 全国2連率の平均的な値
DEFAULT_LOCAL_PLACE2 = 30.0      # 当地2連率の平均的な値
DEFAULT_MOTOR_PLACE2 = 33.0      # モーター2連率の平均的な値
DEFAULT_BOAT_PLACE2 = 34.0       # ボート2連率の平均的な値
DEFAULT_AVG_ST = 0.18            # 平均スタートタイム


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


def _venue_bias(venue_id):
    table = {
        "01": {"inner": 0.94, "outer": 1.10},
        "06": {"inner": 0.90, "outer": 1.18},
        "12": {"inner": 0.95, "outer": 1.10},
        "18": {"inner": 0.90, "outer": 1.20},
        "24": {"inner": 1.05, "outer": 0.95},
    }
    return table.get(str(venue_id).zfill(2), {"inner": 1.0, "outer": 1.0})


def _lane_score(lane, venue_bias):
    lane = _to_int(lane)
    table = {
        1: 3.2,
        2: 3.1,
        3: 3.1,
        4: 3.0,
        5: 2.4,
        6: 1.8,
    }
    score = table.get(lane, 0.0)
    if lane == 1:
        score *= venue_bias["inner"]
    elif lane >= 4:
        score *= venue_bias["outer"]
    return score


def _class_score(c):
    return {
        1: 4.5,
        2: 3.0,
        3: 1.6,
        4: 0.6,
    }.get(_to_int(c), 0.5)


def _st_score(st):
    # NULLの場合はデフォルト値で補完（スコア0扱い）
    if st is None or st == "":
        return 0.0
    st = _to_float(st, DEFAULT_AVG_ST)
    return max(0.0, (0.18 - st) * 46.0)


def _two_rate_score(nat, loc):
    # NULLの場合は平均値で補完
    nat = _to_float(nat, DEFAULT_NATIONAL_PLACE2) if nat is not None else DEFAULT_NATIONAL_PLACE2
    loc = _to_float(loc, DEFAULT_LOCAL_PLACE2) if loc is not None else DEFAULT_LOCAL_PLACE2
    return (nat * 0.55 + loc * 0.45) / 7.2


def _motor_score(m):
    # NULLの場合は平均値で補完
    val = _to_float(m, DEFAULT_MOTOR_PLACE2) if m is not None else DEFAULT_MOTOR_PLACE2
    return val / 38.0


def _boat_score(b):
    # NULLの場合は平均値で補完
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


def _outside_attack(lane, avg_st, ex, venue_bias):
    lane = _to_int(lane)
    # avg_stがNULLの場合はデフォルト値
    st = _to_float(avg_st, DEFAULT_AVG_ST) if avg_st is not None else DEFAULT_AVG_ST
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
    return score * venue_bias["outer"]


def _third_bias(lane, avg_st, nat, loc, ex, venue_bias):
    lane = _to_int(lane)
    st = _to_float(avg_st, DEFAULT_AVG_ST) if avg_st is not None else DEFAULT_AVG_ST
    nat = _to_float(nat, DEFAULT_NATIONAL_PLACE2) if nat is not None else DEFAULT_NATIONAL_PLACE2
    loc = _to_float(loc, DEFAULT_LOCAL_PLACE2) if loc is not None else DEFAULT_LOCAL_PLACE2
    mix = nat * 0.55 + loc * 0.45
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
        score *= venue_bias["outer"]
    return score


def build_entry_features(context):
    entries = context.get("entries", [])
    ex_map = context.get("exhibition", {}) or {}

    venue_id = str(context.get("venue_id", "")).zfill(2)
    venue_bias = _venue_bias(venue_id)
    rank_map = _build_rank_map(ex_map)

    rows = []

    for e in entries:
        lane = _to_int(e.get("lane"))
        ex = ex_map.get(str(lane), {})

        nat2 = e.get("national_place2_rate") or e.get("national_2rate")
        loc2 = e.get("local_place2_rate") or e.get("local_2rate")
        avg_st = e.get("avg_st") or e.get("average_st") or e.get("national_avg_st")
        motor2 = e.get("motor_place2_rate") or e.get("motor_2rate")
        boat2 = e.get("boat_place2_rate") or e.get("boat_2rate")

        score = (
            _lane_score(lane, venue_bias)
            + _class_score(e.get("racer_class"))
            + _st_score(avg_st)
            + _two_rate_score(nat2, loc2)
            + _motor_score(motor2)
            + _boat_score(boat2)
            + _outside_attack(lane, avg_st, ex, venue_bias)
            + _third_bias(lane, avg_st, nat2, loc2, ex, venue_bias)
            + _ex_score(ex, rank_map)
            + _tilt_score(ex)
            + _start_timing_score(ex)
            - _penalty(e.get("f_count"), e.get("l_count"))
        )

        rows.append({
            "lane": lane,
            "score": round(score, 4),
        })

    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows