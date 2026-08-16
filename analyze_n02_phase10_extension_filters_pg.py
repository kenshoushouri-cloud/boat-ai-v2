# -*- coding: utf-8 -*-
"""
analyze_n02_phase10_extension_filters_pg.py

Phase10:
Phase9と同じEXTENSION母集団に、Phase7/8で既に固定済みの補助条件だけを適用し、
追加買い目として採用可能な層があるかを検証する。

重要:
- DB更新なし
- LINE通知なし
- 本番判定変更なし
- Phase9のCORE/EXT定義を変更しない
- 新しい閾値探索なし
- 既存固定閾値のみ使用
- OOS1/OOS2を見て閾値を動かさない

CORE:
  N02_WIND_LT4
  pr 11-20 / mr 2-5 / odds 3-6 / R07-10 / EV MAX / wind<4

EXTENSION:
  CORE候補が存在しないレースだけ
  pr 11-25 / mr 2-5 / odds 3-6 / R07-12 / EV MAX / wind<4

固定補助条件:
  A MOTOR_EDGE   : motor3_vs_field >= 5.3096
  B HEAD_MOTOR3  : head_motor3 >= 54.2408
  C HEAD_AVG_ST  : head_avg_st <= 0.1500

比較:
  EXT_BASE
  EXT_A
  EXT_B
  EXT_C
  EXT_A_OR_B
  EXT_A_OR_C
  EXT_B_OR_C
  EXT_ANY        (= A or B or C)
  EXT_SCORE_2P   (= 3条件中2つ以上)
  EXT_SCORE_3    (= 3条件すべて)

また CORE + 各EXT を比較し、
100円固定でROI・利益・30日購入数・30日利益・最大DD・連敗・月別安定性を確認する。
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Dict, List, Optional

from db_pg import fetch_all
import v24_pre_candidate_notifier_pg as v24

VERSION = "2026-08-17 phase10-extension-fixed-filters-v1"

START = os.getenv("P10_START_DATE", "2025-07-01")
END = os.getenv("P10_END_DATE", "2026-08-15")

TRAIN_END = "2026-03-01"
VALID_END = "2026-05-01"
OOS1_START = "2026-07-01"
OOS2_START = "2026-08-01"

LABELS = [
    "historical", "final_ab", "final", "manual",
    "beforeinfo", "pre", "day", "night", "morning"
]

TH_MOTOR_EDGE = 5.3096
TH_HEAD_MOTOR3 = 54.2408
TH_HEAD_AVG_ST = 0.1500

def sf(v, d=None):
    try:
        return float(v) if v not in (None, "") else d
    except Exception:
        return d

def si(v, d=0):
    try:
        return int(float(v)) if v not in (None, "") else d
    except Exception:
        return d

def nxt(s):
    return (datetime.strptime(s, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

def months(a, b):
    d = datetime.strptime(a[:7] + "-01", "%Y-%m-%d")
    e = datetime.strptime(b[:7] + "-01", "%Y-%m-%d")
    while d <= e:
        yield d.strftime("%Y-%m-01")
        d = d.replace(year=d.year + 1, month=1) if d.month == 12 else d.replace(month=d.month + 1)

def mend(s):
    d = datetime.strptime(s, "%Y-%m-%d")
    d = d.replace(year=d.year + 1, month=1) if d.month == 12 else d.replace(month=d.month + 1)
    return d.strftime("%Y-%m-%d")

def period(ds):
    if ds < TRAIN_END:
        return "TRAIN"
    if ds < VALID_END:
        return "VALID"
    if ds < OOS1_START:
        return "TEST"
    if ds < OOS2_START:
        return "OOS1"
    return "OOS2"

def day_count(a, b):
    return (
        datetime.strptime(b, "%Y-%m-%d").date()
        - datetime.strptime(a, "%Y-%m-%d").date()
    ).days + 1

def lp(x):
    try:
        return LABELS.index(str(x or "").lower())
    except Exception:
        return 999

def choose_label(xb, wb, cb):
    ls = [
        l for l, lanes in xb.items()
        if len(lanes) == 6 and l in wb and len(cb.get(l, {})) == 6
    ]
    return sorted(ls, key=lambda x: (lp(x), x))[0] if ls else None

def metrics(rows, days=None):
    n = len(rows)
    hits = sum(int(x["hit"]) for x in rows)
    ret = sum(int(x["ret"]) for x in rows)
    inv = n * 100

    cur = ls = bank = peak = dd = 0
    for x in sorted(rows, key=lambda z: (z["date"], z["race_id"])):
        if x["hit"]:
            cur = 0
        else:
            cur += 1
            ls = max(ls, cur)

        bank += x["ret"] - 100
        peak = max(peak, bank)
        dd = max(dd, peak - bank)

    out = {
        "n": n,
        "hits": hits,
        "roi": ret / inv * 100 if inv else 0.0,
        "profit": ret - inv,
        "ls": ls,
        "dd": dd,
        "active": len({x["date"] for x in rows}),
    }
    if days:
        out["bets30"] = n / days * 30.44
        out["profit30"] = (ret - inv) / days * 30.44
        out["daysbet"] = days / n if n else 0.0
        out["active_pct"] = out["active"] / days * 100
    else:
        out["bets30"] = 0.0
        out["profit30"] = 0.0
        out["daysbet"] = 0.0
        out["active_pct"] = 0.0
    return out

def fm(m):
    return (
        f"n={m['n']} hits={m['hits']} ROI={m['roi']:.1f}% "
        f"P={m['profit']} LS={m['ls']} DD={m['dd']}"
    )

def match(row, pr_hi):
    pr = si(row.get("prob_rank"), 999)
    mr = si(row.get("market_rank"), 999)
    o = sf(row.get("odds"), 0) or 0
    return 11 <= pr <= pr_hi and 2 <= mr <= 5 and 3.0 <= o < 6.0

def select(rows):
    if not rows:
        return None
    return max(
        rows,
        key=lambda r: (
            sf(r.get("raw_ev"), 0) or 0,
            sf(r.get("prob"), 0) or 0
        )
    )

def valid(v, lo, hi):
    x = sf(v, None)
    if x is None or not (lo <= x <= hi):
        return None
    return x

def aux_features(entries: List[Dict[str, Any]], head: int) -> Dict[str, Any]:
    by = v24._entry_by_lane(entries)
    h = by.get(head)
    if not h:
        return {}

    others = [by[i] for i in range(1, 7) if i != head and i in by]
    if len(others) != 5:
        return {}

    head_avg_st = valid(h.get("avg_st"), 0.01, 0.60)
    head_motor3 = valid(h.get("motor_place3_rate"), 0.01, 100.0)

    other_motor3 = [
        valid(e.get("motor_place3_rate"), 0.01, 100.0)
        for e in others
    ]
    other_motor3 = [x for x in other_motor3 if x is not None]
    other_m3_mean = mean(other_motor3) if len(other_motor3) >= 4 else None

    motor3_vs_field = (
        head_motor3 - other_m3_mean
        if head_motor3 is not None and other_m3_mean is not None
        else None
    )

    A = bool(motor3_vs_field is not None and motor3_vs_field >= TH_MOTOR_EDGE)
    B = bool(head_motor3 is not None and head_motor3 >= TH_HEAD_MOTOR3)
    C = bool(head_avg_st is not None and head_avg_st <= TH_HEAD_AVG_ST)

    return {
        "motor3_vs_field": motor3_vs_field,
        "head_motor3": head_motor3,
        "head_avg_st": head_avg_st,
        "A": A,
        "B": B,
        "C": C,
        "score": int(A) + int(B) + int(C),
    }

def passes(name: str, r: Dict[str, Any]) -> bool:
    a = r["aux"]["A"]
    b = r["aux"]["B"]
    c = r["aux"]["C"]
    s = r["aux"]["score"]

    if name == "EXT_BASE":
        return True
    if name == "EXT_A":
        return a
    if name == "EXT_B":
        return b
    if name == "EXT_C":
        return c
    if name == "EXT_A_OR_B":
        return a or b
    if name == "EXT_A_OR_C":
        return a or c
    if name == "EXT_B_OR_C":
        return b or c
    if name == "EXT_ANY":
        return a or b or c
    if name == "EXT_SCORE_2P":
        return s >= 2
    if name == "EXT_SCORE_3":
        return s >= 3
    return False

FILTERS = [
    "EXT_BASE",
    "EXT_A",
    "EXT_B",
    "EXT_C",
    "EXT_A_OR_B",
    "EXT_A_OR_C",
    "EXT_B_OR_C",
    "EXT_ANY",
    "EXT_SCORE_2P",
    "EXT_SCORE_3",
]

def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です")

    print(f"✅ analyze_n02_phase10_extension_filters_pg.py VERSION {VERSION}", flush=True)
    print(f"PERIOD={START}..{END}", flush=True)
    print("Phase9 EXT母集団を固定し、Phase7/8既存閾値のみ適用。新規探索なし。", flush=True)

    core = []
    ext = []

    for ms in months(START, END):
        a = max(START, ms)
        b = min(nxt(END), mend(ms))
        ra = a.replace("-", "")
        rb = b.replace("-", "")

        races = fetch_all(
            "select * from v2_races "
            "where race_date >= %s and race_date < %s "
            "order by race_date,venue_id,race_no",
            (a, b),
        )
        er = fetch_all(
            "select * from v2_race_entries "
            "where race_id >= %s and race_id < %s "
            "order by race_id,lane",
            (ra, rb),
        )
        oo = fetch_all(
            "select race_id,ticket,odds from v2_odds_trifecta "
            "where race_id >= %s and race_id < %s",
            (ra, rb),
        )
        rr = fetch_all(
            "select race_id,trifecta_ticket,"
            "coalesce(trifecta_payout_yen,trifecta_payout) payout "
            "from v2_results "
            "where race_id >= %s and race_id < %s",
            (ra, rb),
        )
        ex = fetch_all(
            "select race_id,snapshot_label,lane,exhibition_time "
            "from v2_realtime_exhibition_snapshots "
            "where race_id >= %s and race_id < %s",
            (ra, rb),
        )
        ww = fetch_all(
            "select race_id,snapshot_label,wind_speed_m "
            "from v2_realtime_weather_snapshots "
            "where race_id >= %s and race_id < %s",
            (ra, rb),
        )
        cc = fetch_all(
            "select race_id,snapshot_label,lane "
            "from v2_realtime_racer_condition_snapshots "
            "where race_id >= %s and race_id < %s",
            (ra, rb),
        )

        eb = defaultdict(list)
        for x in er:
            eb[str(x.get("race_id") or "")].append(x)

        ob = defaultdict(dict)
        for x in oo:
            t = v24._norm_ticket(x.get("ticket"))
            o = sf(x.get("odds"), 0)
            rid = str(x.get("race_id") or "")
            if rid and t and o and o > 0:
                ob[rid][t] = o

        rb = {}
        for x in rr:
            rid = str(x.get("race_id") or "")
            t = v24._norm_ticket(x.get("trifecta_ticket"))
            p = si(x.get("payout"), 0)
            if rid and t and p > 0:
                rb[rid] = (t, p)

        xb = defaultdict(lambda: defaultdict(set))
        for x in ex:
            rid = str(x.get("race_id") or "")
            l = str(x.get("snapshot_label") or "")
            lane = si(x.get("lane"), 0)
            if rid and l and 1 <= lane <= 6 and x.get("exhibition_time") is not None:
                xb[rid][l].add(lane)

        wb = defaultdict(dict)
        for x in ww:
            rid = str(x.get("race_id") or "")
            l = str(x.get("snapshot_label") or "")
            if rid and l:
                wb[rid][l] = x

        cb = defaultdict(lambda: defaultdict(dict))
        for x in cc:
            rid = str(x.get("race_id") or "")
            l = str(x.get("snapshot_label") or "")
            lane = si(x.get("lane"), 0)
            if rid and l and 1 <= lane <= 6:
                cb[rid][l][lane] = x

        mn_core = 0
        mn_ext = 0

        for race in races:
            rid = str(race.get("race_id") or "")
            ent = eb.get(rid, [])
            odds = ob.get(rid, {})
            res = rb.get(rid)

            if len(v24._entry_by_lane(ent)) != 6 or not res:
                continue

            ok, _ = v24._validate_odds_snapshot(odds)
            if not ok:
                continue

            lab = choose_label(xb.get(rid, {}), wb.get(rid, {}), cb.get(rid, {}))
            if not lab:
                continue

            wind = sf(wb[rid][lab].get("wind_speed_m"), None)
            if wind is None or wind >= 4:
                continue

            rno = si(race.get("race_no"), 0)
            venue = str(
                race.get("venue_id") or race.get("venue_code") or ""
            ).zfill(2)

            ranked = v24._rank_candidates(ent, venue, odds)

            core_sel = None
            if 7 <= rno <= 10:
                core_sel = select([z for z in ranked if match(z, 20)])

            if core_sel:
                ticket = str(core_sel.get("ticket") or "")
                rt, pay = res
                core.append({
                    "race_id": rid,
                    "date": str(race.get("race_date"))[:10],
                    "ticket": ticket,
                    "hit": ticket == rt,
                    "ret": pay if ticket == rt else 0,
                })
                mn_core += 1
                continue

            if 7 <= rno <= 12:
                ext_sel = select([z for z in ranked if match(z, 25)])
                if ext_sel:
                    ticket = str(ext_sel.get("ticket") or "")
                    head = si(ticket.split("-")[0], 0)
                    aux = aux_features(ent, head)
                    if not aux:
                        continue

                    rt, pay = res
                    ext.append({
                        "race_id": rid,
                        "date": str(race.get("race_date"))[:10],
                        "ticket": ticket,
                        "hit": ticket == rt,
                        "ret": pay if ticket == rt else 0,
                        "aux": aux,
                    })
                    mn_ext += 1

        print(f"month={ms[:7]} core={mn_core} extension={mn_ext}", flush=True)

    days = day_count(START, END)

    ext_sets = {
        name: [r for r in ext if passes(name, r)]
        for name in FILTERS
    }

    print("\n" + "=" * 108, flush=True)
    print("=== EXTENSION FILTER COMPARISON @100yen ===", flush=True)
    for name in FILTERS:
        m = metrics(ext_sets[name], days)
        print(
            f"{name}: {fm(m)} "
            f"bets/30d={m['bets30']:.2f} "
            f"days/bet={m['daysbet']:.2f} "
            f"profit/30d={m['profit30']:.0f}",
            flush=True,
        )

    print("\n=== PERIOD COMPARISON: EXT only ===", flush=True)
    for p in ("TRAIN", "VALID", "TEST", "OOS1", "OOS2"):
        print(f"\n--- {p} ---", flush=True)
        for name in FILTERS:
            seg = [r for r in ext_sets[name] if period(r["date"]) == p]
            print(f"{name}: {fm(metrics(seg))}", flush=True)

    print("\n" + "=" * 108, flush=True)
    print("=== CORE + FILTERED EXT ===", flush=True)
    core_m = metrics(core, days)
    print(
        f"CORE_ONLY: {fm(core_m)} "
        f"bets/30d={core_m['bets30']:.2f} "
        f"profit/30d={core_m['profit30']:.0f}",
        flush=True,
    )

    for name in FILTERS:
        if name == "EXT_BASE":
            label = "CORE_PLUS_EXT_BASE"
        else:
            label = "CORE_PLUS_" + name.replace("EXT_", "")
        union = core + ext_sets[name]
        m = metrics(union, days)
        print(
            f"{label}: {fm(m)} "
            f"bets/30d={m['bets30']:.2f} "
            f"days/bet={m['daysbet']:.2f} "
            f"profit/30d={m['profit30']:.0f}",
            flush=True,
        )

    print("\n" + "=" * 108, flush=True)
    print("=== MONTHLY STABILITY: selected EXT filters ===", flush=True)
    selected_for_monthly = [
        "EXT_BASE", "EXT_A", "EXT_B", "EXT_C",
        "EXT_ANY", "EXT_SCORE_2P", "EXT_SCORE_3"
    ]
    mos = sorted({r["date"][:7] for r in core + ext})
    plus = {name: 0 for name in selected_for_monthly}

    for mo in mos:
        parts = [mo]
        for name in selected_for_monthly:
            seg = [r for r in ext_sets[name] if r["date"].startswith(mo)]
            m = metrics(seg)
            if m["profit"] > 0:
                plus[name] += 1
            parts.append(f"{name}:n={m['n']} ROI={m['roi']:.0f}% P={m['profit']}")
        print(" | ".join(parts), flush=True)

    print("\npositive_month_ratio", flush=True)
    for name in selected_for_monthly:
        ratio = plus[name] / len(mos) * 100 if mos else 0.0
        print(f"{name}: {plus[name]}/{len(mos)} = {ratio:.1f}%", flush=True)

    print("\n" + "=" * 108, flush=True)
    print("=== AUX SCORE DISTRIBUTION ===", flush=True)
    for score in (0, 1, 2, 3):
        rr = [r for r in ext if r["aux"]["score"] == score]
        print(f"score={score}: {fm(metrics(rr))}", flush=True)

    print("\n=== FIXED-FILTER OOS CHECK ===", flush=True)
    for name in FILTERS:
        pre = [r for r in ext_sets[name] if r["date"] < OOS1_START]
        o1 = [r for r in ext_sets[name] if period(r["date"]) == "OOS1"]
        o2 = [r for r in ext_sets[name] if period(r["date"]) == "OOS2"]
        pm = metrics(pre)
        m1 = metrics(o1)
        m2 = metrics(o2)
        print(
            f"{name}: PRE n={pm['n']} ROI={pm['roi']:.1f}% "
            f"OOS1 n={m1['n']} ROI={m1['roi']:.1f}% "
            f"OOS2 n={m2['n']} ROI={m2['roi']:.1f}%",
            flush=True,
        )

    print("\nIMPORTANT:", flush=True)
    print("- OOS1/OOS2を見て閾値は変更しません。", flush=True)
    print("- EXT_BASEより頻度が減っても、TEST/OOSで安定しないfilterは採用しません。", flush=True)
    print("- COREは一切変更していません。", flush=True)
    print("=== phase10 finished ===", flush=True)

if __name__ == "__main__":
    main()