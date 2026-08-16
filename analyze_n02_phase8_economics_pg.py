# -*- coding: utf-8 -*-
"""
analyze_n02_phase8_economics_pg.py

Phase 8:
Phase 7で固定したN02/WIND_LT4系候補について、
「回収率」「100円固定の利益」「購入頻度」「購入日数」「最大DD」「連敗」を
同じ土俵で比較する読み取り専用スクリプト。

重要:
- DB更新なし
- LINE通知なし
- 本番判定変更なし
- Phase7で固定した閾値をそのまま使う
- 閾値の再最適化はしない
- 2026-07/08のOOSを見て閾値を変更しない
- 新しい総当たり探索は行わない

固定比較:
  A. N02_WIND_LT4
  B. MOTOR_EDGE
     motor3_vs_field >= 5.3096
  C. HEAD_MOTOR3
     head_motor3 >= 54.2408
  D. HEAD_AVG_ST
     head_avg_st <= 0.1500

追加監査:
- モーター「交換直後/データ初期」の代理指標として、
  DB内でその会場×motor_noが当該レース以前に何走観測されていたか
  motor_prior_starts を算出する。
- これは真の使用開始日ではなく「DB内で観測できた過去走数」。
- 2025-07-01以前から使われていたモーターは左打ち切りになるため、
  本番のモーター交換日判定の代替ではない。
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, List, Optional

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-17 phase8-economics-v1"

START_DATE = os.getenv("P8_START_DATE", "2025-07-01")
END_DATE = os.getenv("P8_END_DATE", "2026-08-15")

TRAIN_END = "2026-03-01"
VALID_END = "2026-05-01"
OOS1_START = "2026-07-01"
OOS2_START = "2026-08-01"

RULE = {
    "pr": (11, 20),
    "mr": (2, 5),
    "odds": (3.0, 6.0),
    "race_nos": {7, 8, 9, 10},
}
LABEL_PRIORITY = [
    "historical", "final_ab", "final", "manual",
    "beforeinfo", "pre", "day", "night", "morning",
]

STRATEGIES = {
    "N02_WIND_LT4": lambda r: True,
    "MOTOR_EDGE": lambda r: (
        r["features"].get("motor3_vs_field") is not None
        and r["features"]["motor3_vs_field"] >= 5.3096
    ),
    "HEAD_MOTOR3": lambda r: (
        r["features"].get("head_motor3") is not None
        and r["features"]["head_motor3"] >= 54.2408
    ),
    "HEAD_AVG_ST": lambda r: (
        r["features"].get("head_avg_st") is not None
        and r["features"]["head_avg_st"] <= 0.1500
    ),
}

def sf(v: Any, d=None):
    try:
        if v is None or v == "":
            return d
        return float(v)
    except Exception:
        return d

def si(v: Any, d=0):
    try:
        if v is None or v == "":
            return d
        return int(float(v))
    except Exception:
        return d

def next_day(s: str) -> str:
    return (datetime.strptime(s, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

def month_starts(a: str, b: str):
    cur = datetime.strptime(a[:7] + "-01", "%Y-%m-%d")
    end = datetime.strptime(b[:7] + "-01", "%Y-%m-%d")
    while cur <= end:
        yield cur.strftime("%Y-%m-01")
        if cur.month == 12:
            cur = cur.replace(year=cur.year + 1, month=1)
        else:
            cur = cur.replace(month=cur.month + 1)

def month_end(s: str) -> str:
    d = datetime.strptime(s, "%Y-%m-%d")
    if d.month == 12:
        d = d.replace(year=d.year + 1, month=1)
    else:
        d = d.replace(month=d.month + 1)
    return d.strftime("%Y-%m-%d")

def period_name(ds: str) -> str:
    if ds < TRAIN_END:
        return "TRAIN"
    if ds < VALID_END:
        return "VALID"
    if ds < OOS1_START:
        return "TEST"
    if ds < OOS2_START:
        return "OOS1"
    return "OOS2"

def date_days(a: str, b: str) -> int:
    da = datetime.strptime(a, "%Y-%m-%d").date()
    db = datetime.strptime(b, "%Y-%m-%d").date()
    return (db - da).days + 1

def qtile(vals: List[int], q: float) -> Optional[float]:
    xs = sorted(vals)
    if not xs:
        return None
    if len(xs) == 1:
        return float(xs[0])
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1-frac) + xs[hi] * frac

def metrics(rows: List[Dict[str, Any]], calendar_days: Optional[int] = None) -> Dict[str, Any]:
    n = len(rows)
    hits = sum(int(r["hit"]) for r in rows)
    ret = sum(int(r["ret"]) for r in rows)
    inv = n * 100

    longest = cur = 0
    bankroll = peak = maxdd = 0
    for r in sorted(rows, key=lambda x: (x["date"], x["race_id"])):
        if r["hit"]:
            cur = 0
        else:
            cur += 1
            longest = max(longest, cur)

        bankroll += int(r["ret"]) - 100
        peak = max(peak, bankroll)
        maxdd = max(maxdd, peak - bankroll)

    active_days = len({r["date"] for r in rows})
    out = {
        "n": n,
        "hits": hits,
        "hit_rate": hits / n * 100 if n else 0.0,
        "roi": ret / inv * 100 if inv else 0.0,
        "profit": ret - inv,
        "invest": inv,
        "return": ret,
        "lose_streak": longest,
        "maxdd": maxdd,
        "active_days": active_days,
    }

    if calendar_days:
        out["bets_per_day"] = n / calendar_days
        out["days_per_bet"] = calendar_days / n if n else 0.0
        out["bets_per_30d"] = n / calendar_days * 30.44
        out["profit_per_30d"] = (ret - inv) / calendar_days * 30.44
        out["active_day_pct"] = active_days / calendar_days * 100
    else:
        out["bets_per_day"] = 0.0
        out["days_per_bet"] = 0.0
        out["bets_per_30d"] = 0.0
        out["profit_per_30d"] = 0.0
        out["active_day_pct"] = 0.0
    return out

def fmt(m: Dict[str, Any]) -> str:
    return (
        f"n={m['n']} hits={m['hits']} hit={m['hit_rate']:.1f}% "
        f"ROI={m['roi']:.1f}% profit={m['profit']} "
        f"LS={m['lose_streak']} DD={m['maxdd']}"
    )

def label_priority(label: str) -> int:
    s = str(label or "").strip().lower()
    try:
        return LABEL_PRIORITY.index(s)
    except ValueError:
        return len(LABEL_PRIORITY) + 100

def choose_weather_label(exh_labels, weather_labels, cond_labels):
    common = []
    for label, lanes in exh_labels.items():
        if len(lanes) == 6 and label in weather_labels and len(cond_labels.get(label, {})) == 6:
            common.append(label)
    if not common:
        return None
    return sorted(common, key=lambda x: (label_priority(x), str(x)))[0]

def fetch_month(ms: str, mx: str):
    a = max(START_DATE, ms)
    b = min(next_day(END_DATE), mx)
    if a >= b:
        return [], [], [], [], [], [], []

    ra, rb = a.replace("-", ""), b.replace("-", "")

    races = fetch_all(
        "select * from v2_races "
        "where race_date >= %s and race_date < %s "
        "order by race_date,venue_id,race_no",
        (a, b),
    )
    entries = fetch_all(
        "select * from v2_race_entries "
        "where race_id >= %s and race_id < %s "
        "order by race_id,lane",
        (ra, rb),
    )
    odds = fetch_all(
        "select race_id,ticket,odds from v2_odds_trifecta "
        "where race_id >= %s and race_id < %s "
        "order by race_id,ticket",
        (ra, rb),
    )
    results = fetch_all(
        "select race_id,trifecta_ticket,"
        "coalesce(trifecta_payout_yen,trifecta_payout) payout "
        "from v2_results "
        "where race_id >= %s and race_id < %s",
        (ra, rb),
    )
    exh = fetch_all(
        "select race_id,snapshot_label,lane,exhibition_time "
        "from v2_realtime_exhibition_snapshots "
        "where race_id >= %s and race_id < %s "
        "order by race_id,snapshot_label,lane",
        (ra, rb),
    )
    weather = fetch_all(
        "select race_id,snapshot_label,wind_speed_m "
        "from v2_realtime_weather_snapshots "
        "where race_id >= %s and race_id < %s "
        "order by race_id,snapshot_label,snapshot_at",
        (ra, rb),
    )
    cond = fetch_all(
        "select race_id,snapshot_label,lane "
        "from v2_realtime_racer_condition_snapshots "
        "where race_id >= %s and race_id < %s "
        "order by race_id,snapshot_label,lane",
        (ra, rb),
    )
    return races, entries, odds, results, exh, weather, cond

def valid_rate(v: Any, lo: float, hi: float) -> Optional[float]:
    x = sf(v, None)
    if x is None or not (lo <= x <= hi):
        return None
    return x

def feature_row(entries: List[Dict[str, Any]], head: int) -> Dict[str, Optional[float]]:
    by = v24._entry_by_lane(entries)
    h = by.get(head)
    if not h:
        return {}

    others = [by[i] for i in range(1,7) if i != head and i in by]
    if len(others) != 5:
        return {}

    def val(e, key, lo, hi):
        return valid_rate(e.get(key), lo, hi)

    def avg_other(key, lo, hi):
        vals = [val(e, key, lo, hi) for e in others]
        vals = [x for x in vals if x is not None]
        return mean(vals) if len(vals) >= 4 else None

    st = val(h, "avg_st", 0.01, 0.60)
    m3 = val(h, "motor_place3_rate", 0.01, 100.0)
    om3 = avg_other("motor_place3_rate", 0.01, 100.0)

    return {
        "head_avg_st": st,
        "head_motor3": m3,
        "motor3_vs_field": (m3 - om3) if m3 is not None and om3 is not None else None,
    }

def match_n02(row: Dict[str, Any]) -> bool:
    return (
        RULE["pr"][0] <= si(row.get("prob_rank"), 999) <= RULE["pr"][1]
        and RULE["mr"][0] <= si(row.get("market_rank"), 999) <= RULE["mr"][1]
        and RULE["odds"][0] <= (sf(row.get("odds"), 0) or 0) < RULE["odds"][1]
    )

def select_ev(rows):
    if not rows:
        return None
    return max(
        rows,
        key=lambda r: (
            sf(r.get("raw_ev"), 0) or 0,
            sf(r.get("prob"), 0) or 0,
        ),
    )

def print_strategy(name: str, rows: List[Dict[str, Any]], total_days: int):
    m = metrics(rows, total_days)
    print(
        f"{name}: {fmt(m)} "
        f"purchase_days={m['active_days']}/{total_days} "
        f"active_day_pct={m['active_day_pct']:.1f}% "
        f"bets_per_30d={m['bets_per_30d']:.2f} "
        f"days_per_bet={m['days_per_bet']:.2f} "
        f"profit_per_30d={m['profit_per_30d']:.0f}",
        flush=True,
    )

def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")

    total_days = date_days(START_DATE, END_DATE)

    print(f"✅ analyze_n02_phase8_economics_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START_DATE}..{END_DATE} days={total_days}", flush=True)
    print("読み取り専用。Phase7固定条件の経済性・頻度比較のみ。", flush=True)

    rows_all = []
    motor_seen = defaultdict(int)  # (venue, motor_no) -> prior observed starts

    for ms in month_starts(START_DATE, END_DATE):
        races, entries, odds, results, exh, weather, cond = fetch_month(ms, month_end(ms))

        eb = defaultdict(list)
        for x in entries:
            eb[str(x.get("race_id") or "")].append(x)

        ob = defaultdict(dict)
        for x in odds:
            rid = str(x.get("race_id") or "")
            t = v24._norm_ticket(x.get("ticket"))
            o = sf(x.get("odds"), 0)
            if rid and t and o and o > 0:
                ob[rid][t] = o

        rb = {}
        for x in results:
            rid = str(x.get("race_id") or "")
            t = v24._norm_ticket(x.get("trifecta_ticket"))
            p = si(x.get("payout"), 0)
            if rid and t and p > 0:
                rb[rid] = (t, p)

        xb = defaultdict(lambda: defaultdict(set))
        for x in exh:
            rid = str(x.get("race_id") or "")
            lab = str(x.get("snapshot_label") or "")
            lane = si(x.get("lane"), 0)
            if rid and lab and 1 <= lane <= 6 and x.get("exhibition_time") is not None:
                xb[rid][lab].add(lane)

        wb = defaultdict(dict)
        for x in weather:
            rid = str(x.get("race_id") or "")
            lab = str(x.get("snapshot_label") or "")
            if rid and lab:
                wb[rid][lab] = x

        cb = defaultdict(lambda: defaultdict(dict))
        for x in cond:
            rid = str(x.get("race_id") or "")
            lab = str(x.get("snapshot_label") or "")
            lane = si(x.get("lane"), 0)
            if rid and lab and 1 <= lane <= 6:
                cb[rid][lab][lane] = x

        month_n02 = 0

        for race in races:
            rid = str(race.get("race_id") or "")
            venue = str(race.get("venue_id") or race.get("venue_code") or "").zfill(2)
            ent = eb.get(rid, [])
            odd = ob.get(rid, {})
            res = rb.get(rid)

            # candidate evaluation BEFORE incrementing motor_seen:
            if len(v24._entry_by_lane(ent)) == 6 and res:
                ok, _ = v24._validate_odds_snapshot(odd)
                lab = choose_weather_label(xb.get(rid, {}), wb.get(rid, {}), cb.get(rid, {})) if ok else None

                rno = si(race.get("race_no"), 0)
                if ok and lab and rno in RULE["race_nos"]:
                    ranked = v24._rank_candidates(ent, venue, odd)
                    sel = select_ev([x for x in ranked if match_n02(x)])

                    if sel:
                        ticket = str(sel.get("ticket") or "")
                        head = si(ticket.split("-")[0], 0)
                        by = v24._entry_by_lane(ent)
                        h = by.get(head)
                        feats = feature_row(ent, head)

                        if h and feats:
                            wind = sf(wb[rid][lab].get("wind_speed_m"), None)
                            if wind is not None and wind < 4.0:
                                motor_no = str(h.get("motor_no") or "").strip()
                                prior = motor_seen[(venue, motor_no)] if motor_no else None

                                rt, payout = res
                                hit = ticket == rt

                                rows_all.append({
                                    "race_id": rid,
                                    "date": str(race.get("race_date") or "")[:10],
                                    "venue": venue,
                                    "race_no": rno,
                                    "ticket": ticket,
                                    "head": head,
                                    "hit": hit,
                                    "ret": payout if hit else 0,
                                    "features": feats,
                                    "motor_no": motor_no,
                                    "motor_prior_starts": prior,
                                })
                                month_n02 += 1

            # increment after evaluation => no future/same-race leakage
            for e in ent:
                motor_no = str(e.get("motor_no") or "").strip()
                if motor_no:
                    motor_seen[(venue, motor_no)] += 1

        print(f"month={ms[:7]} N02_WIND_LT4={month_n02}", flush=True)

    strategy_rows = {
        name: [r for r in rows_all if fn(r)]
        for name, fn in STRATEGIES.items()
    }

    print("\n" + "=" * 100, flush=True)
    print("=== OVERALL ECONOMICS @100yen/bet ===", flush=True)
    for name, rr in strategy_rows.items():
        print_strategy(name, rr, total_days)

    print("\n=== PERIOD COMPARISON ===", flush=True)
    for p in ("TRAIN", "VALID", "TEST", "OOS1", "OOS2"):
        print(f"\n--- {p} ---", flush=True)
        for name, rr in strategy_rows.items():
            seg = [r for r in rr if period_name(r["date"]) == p]
            print(f"{name}: {fmt(metrics(seg))}", flush=True)

    print("\n" + "=" * 100, flush=True)
    print("=== MONTHLY ECONOMICS ===", flush=True)
    months = sorted({r["date"][:7] for r in rows_all})
    positive = {k: 0 for k in STRATEGIES}

    for mo in months:
        parts = [mo]
        for name, rr in strategy_rows.items():
            seg = [r for r in rr if r["date"].startswith(mo)]
            m = metrics(seg)
            if m["profit"] > 0:
                positive[name] += 1
            parts.append(f"{name}:n={m['n']} ROI={m['roi']:.0f}% P={m['profit']}")
        print(" | ".join(parts), flush=True)

    print("\npositive_month_ratio", flush=True)
    for name in STRATEGIES:
        ratio = positive[name] / len(months) * 100 if months else 0.0
        print(f"{name}: {positive[name]}/{len(months)} = {ratio:.1f}%", flush=True)

    print("\n" + "=" * 100, flush=True)
    print("=== STRATEGY OVERLAP ===", flush=True)
    names = list(STRATEGIES)
    sets = {name: {r["race_id"] for r in strategy_rows[name]} for name in names}
    for i, a in enumerate(names):
        for b in names[i+1:]:
            inter = len(sets[a] & sets[b])
            print(f"{a} ∩ {b} = {inter}", flush=True)

    print("\n" + "=" * 100, flush=True)
    print("=== MOTOR DATA CONFIDENCE AUDIT ===", flush=True)
    print("motor_prior_starts = DB内で同じ会場×motor_noを当該レース以前に観測した走数。真の交換後走数ではありません。", flush=True)

    train_motor = [
        r["motor_prior_starts"]
        for r in rows_all
        if period_name(r["date"]) == "TRAIN"
        and r["motor_prior_starts"] is not None
    ]
    q33 = qtile(train_motor, 0.33)
    q67 = qtile(train_motor, 0.67)
    print(f"TRAIN motor_prior_starts terciles: q33={q33:.1f} q67={q67:.1f}", flush=True)

    def bucket(v):
        if v is None:
            return "missing"
        if v <= q33:
            return "LOW_HISTORY"
        if v <= q67:
            return "MID_HISTORY"
        return "HIGH_HISTORY"

    for strategy_name in ("N02_WIND_LT4", "MOTOR_EDGE", "HEAD_MOTOR3"):
        print(f"\n--- {strategy_name} by motor history ---", flush=True)
        rr = strategy_rows[strategy_name]
        for b in ("LOW_HISTORY", "MID_HISTORY", "HIGH_HISTORY", "missing"):
            seg = [r for r in rr if bucket(r["motor_prior_starts"]) == b]
            print(f"{b}: {fmt(metrics(seg))}", flush=True)

    print("\n=== MOTOR_HISTORY × PERIOD for MOTOR_EDGE ===", flush=True)
    rr = strategy_rows["MOTOR_EDGE"]
    for p in ("TRAIN", "VALID", "TEST", "OOS1", "OOS2"):
        print(f"--- {p} ---", flush=True)
        pr = [r for r in rr if period_name(r["date"]) == p]
        for b in ("LOW_HISTORY", "MID_HISTORY", "HIGH_HISTORY"):
            seg = [r for r in pr if bucket(r["motor_prior_starts"]) == b]
            print(f"  {b}: {fmt(metrics(seg))}", flush=True)

    print("\n" + "=" * 100, flush=True)
    print("=== DECISION SUPPORT ===", flush=True)

    for name, rr in strategy_rows.items():
        pre = [r for r in rr if r["date"] < OOS1_START]
        o1 = [r for r in rr if period_name(r["date"]) == "OOS1"]
        o2 = [r for r in rr if period_name(r["date"]) == "OOS2"]
        pm = metrics(pre)
        m1 = metrics(o1)
        m2 = metrics(o2)
        allm = metrics(rr, total_days)

        print(
            f"{name}: PRE_OOS ROI={pm['roi']:.1f}% n={pm['n']} "
            f"OOS1 ROI={m1['roi']:.1f}% n={m1['n']} "
            f"OOS2 ROI={m2['roi']:.1f}% n={m2['n']} "
            f"ALL profit/30d={allm['profit_per_30d']:.0f} "
            f"bets/30d={allm['bets_per_30d']:.2f} "
            f"days/bet={allm['days_per_bet']:.2f}",
            flush=True,
        )

    print("\nIMPORTANT:", flush=True)
    print("- Phase8は比較のみ。本番ロジックは変更しません。", flush=True)
    print("- MOTOR_EDGEの高ROIだけで採用せず、購入頻度・月利益・motor_prior_starts依存も同時に確認します。", flush=True)
    print("- 真のモーター交換初期補正には、今後 motor 使用開始日/実走数の取得を追加するのが理想です。", flush=True)
    print("=== phase8 finished ===", flush=True)

if __name__ == "__main__":
    main()