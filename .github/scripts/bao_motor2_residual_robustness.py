# -*- coding: utf-8 -*-
"""Fine-grid and stability audit for Motor2 residual signal beyond market.

The only promoted entry-level feature from the prior screen was motor_place2_rate.
This audit repeats the expanding train-only selection on a finer beta grid and
reports OOS paired loss differences by split, month, and venue.

r_beta(ticket) ∝ q(ticket) * exp(beta * motor2_ticket_score)

Research only. Historical odds are not guaranteed actionable timestamps.
No DB writes / persistence / Production changes.
"""
from __future__ import annotations

import math
import os
import re
from collections import defaultdict
from datetime import date, timedelta

import psycopg
from psycopg.rows import dict_row

DB = os.getenv("DATABASE_URL", "").strip()
START = date(2025, 7, 1)
END = date(2026, 8, 22)
BETAS = [-0.05, -0.02, 0.00, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15]
SPLITS = [
    (date(2025, 12, 31), date(2026, 1, 1), date(2026, 2, 28)),
    (date(2026, 2, 28), date(2026, 3, 1), date(2026, 4, 30)),
    (date(2026, 4, 30), date(2026, 5, 1), date(2026, 6, 30)),
    (date(2026, 6, 30), date(2026, 7, 1), END),
]
CUTOFF_TO_SPLIT = {x[0]: i for i, x in enumerate(SPLITS)}
EPS = 1e-15
POS_W = (1.0, 0.6, 0.3)


def nt(v):
    xs = re.findall(r"[1-6]", str(v or ""))
    return "-".join(xs[:3]) if len(xs) >= 3 else ""


def nextm(d):
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def sf(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def motor_scores(entries):
    by = {int(e.get("lane") or 0): e for e in entries}
    if set(by) != {1, 2, 3, 4, 5, 6}:
        return None
    vals = []
    for lane in range(1, 7):
        x = sf(by[lane].get("motor_place2_rate"))
        if x is None or not (0 <= x <= 100):
            return None
        vals.append(x)
    mu = sum(vals) / 6.0
    sd = math.sqrt(sum((x - mu) ** 2 for x in vals) / 6.0)
    if sd < 1e-12:
        return None
    z = {lane: (vals[lane - 1] - mu) / sd for lane in range(1, 7)}
    out = {}
    for a in range(1, 7):
        for b in range(1, 7):
            if b == a:
                continue
            for c in range(1, 7):
                if c in (a, b):
                    continue
                out[f"{a}-{b}-{c}"] = POS_W[0] * z[a] + POS_W[1] * z[b] + POS_W[2] * z[c]
    return out


def beta_loss(q, sc, actual, beta):
    if beta == 0.0:
        return -math.log(max(q[actual], EPS))
    den = sum(qq * math.exp(beta * sc[t]) for t, qq in q.items())
    pa = q[actual] * math.exp(beta * sc[actual]) / den
    return -math.log(max(pa, EPS))


def adjusted(q, sc, beta):
    if beta == 0.0:
        return dict(q)
    vals = {t: qq * math.exp(beta * sc[t]) for t, qq in q.items()}
    s = sum(vals.values())
    return {t: v / s for t, v in vals.items()}


def stat_new():
    return {
        "n": 0,
        "m_ll": 0.0,
        "a_ll": 0.0,
        "m_br": 0.0,
        "a_br": 0.0,
        "m_rank": 0.0,
        "a_rank": 0.0,
        "diff_sum": 0.0,
        "diff_sq": 0.0,
    }


def stat_add(s, q, a, actual):
    qm = max(q[actual], EPS)
    qa = max(a[actual], EPS)
    ml = -math.log(qm)
    al = -math.log(qa)
    mb = 1.0 - 2.0 * qm + sum(x * x for x in q.values())
    ab = 1.0 - 2.0 * qa + sum(x * x for x in a.values())
    mr = 1 + sum(1 for x in q.values() if x > qm)
    ar = 1 + sum(1 for x in a.values() if x > qa)
    d = al - ml
    s["n"] += 1
    s["m_ll"] += ml
    s["a_ll"] += al
    s["m_br"] += mb
    s["a_br"] += ab
    s["m_rank"] += mr
    s["a_rank"] += ar
    s["diff_sum"] += d
    s["diff_sq"] += d * d


def stat_merge(dst, src):
    for k in dst:
        dst[k] += src[k]


def stat_fmt(s):
    n = s["n"]
    if not n:
        return "n:0"
    dll = s["diff_sum"] / n
    dbr = s["a_br"] / n - s["m_br"] / n
    dr = s["a_rank"] / n - s["m_rank"] / n
    if n > 1:
        var = max(0.0, (s["diff_sq"] - s["diff_sum"] * s["diff_sum"] / n) / (n - 1))
        se = math.sqrt(var / n)
    else:
        se = 0.0
    z = dll / se if se > 0 else 0.0
    return (
        f"n:{n} market_ll:{s['m_ll']/n:.6f} adjusted_ll:{s['a_ll']/n:.6f} "
        f"delta_ll:{dll:.6f} se:{se:.6f} z:{z:.2f} "
        f"delta_brier:{dbr:.6f} delta_rank:{dr:.2f}"
    )


def split_for_date(rd):
    for i, (_, a, b) in enumerate(SPLITS):
        if a <= rd <= b:
            return i
    return None


def main():
    if not DB:
        raise RuntimeError("DATABASE_URL is required")
    print(f"BAO_M2ROB_MODE=read_only period:{START}..{END}", flush=True)
    print("BAO_M2ROB_BETA_GRID=" + ",".join(f"{x:.2f}" for x in BETAS), flush=True)
    print("BAO_M2ROB_FORMULA=r_beta~q*exp(beta*motor2_ticket_score)", flush=True)
    print("BAO_M2ROB_ODDS_CAVEAT=historical_price_not_proven_actionable_timestamp", flush=True)

    train_loss = {b: 0.0 for b in BETAS}
    train_n = 0
    selected = [None] * len(SPLITS)
    split_stats = [stat_new() for _ in SPLITS]
    month_stats = defaultdict(stat_new)
    venue_stats = defaultdict(stat_new)
    total = complete = motor_ready = 0

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        cur = date(START.year, START.month, 1)
        while cur <= END:
            mx = nextm(cur)
            a = max(START, cur)
            b = min(END + timedelta(days=1), mx)
            key = a.strftime("%Y-%m")
            with conn.cursor() as c:
                c.execute("set statement_timeout='120s'")
                c.execute("""select race_id,race_date,coalesce(venue_id,venue_code) venue_id
                              from v2_races where race_date >= %s and race_date < %s order by race_id""", (a, b))
                races = [dict(x) for x in c.fetchall()]
                c.execute("""select e.race_id,e.lane,e.motor_place2_rate
                              from v2_race_entries e join v2_races r on r.race_id=e.race_id
                              where r.race_date >= %s and r.race_date < %s order by e.race_id,e.lane""", (a, b))
                entries = [dict(x) for x in c.fetchall()]
                c.execute("""select o.race_id,o.ticket,o.odds
                              from v2_odds_trifecta o join v2_races r on r.race_id=o.race_id
                              where r.race_date >= %s and r.race_date < %s and o.odds > 1
                              order by o.race_id,o.ticket""", (a, b))
                odds = [dict(x) for x in c.fetchall()]
                c.execute("""select res.race_id,res.trifecta_ticket
                              from v2_results res join v2_races r on r.race_id=res.race_id
                              where r.race_date >= %s and r.race_date < %s""", (a, b))
                results = {str(x["race_id"]): nt(x["trifecta_ticket"]) for x in c.fetchall()}

            eb = defaultdict(list)
            ob = defaultdict(dict)
            for e in entries:
                eb[str(e["race_id"])].append(e)
            for o in odds:
                t = nt(o["ticket"])
                if t:
                    ob[str(o["race_id"])][t] = float(o["odds"])

            mcomplete = mready = 0
            total += len(races)
            for r in races:
                rid = str(r["race_id"])
                rd = r["race_date"]
                venue = str(r.get("venue_id") or "").zfill(2)
                es = eb.get(rid, [])
                om = ob.get(rid, {})
                actual = results.get(rid, "")
                if len(es) != 6 or len(om) != 120 or actual not in om:
                    continue
                inv = {t: 1.0 / odd for t, odd in om.items() if odd > 1.0}
                if len(inv) != 120:
                    continue
                den = sum(inv.values())
                q = {t: v / den for t, v in inv.items()}
                if actual not in q:
                    continue
                complete += 1
                mcomplete += 1
                sc = motor_scores(es)
                if sc is None:
                    continue
                motor_ready += 1
                mready += 1

                # Expanding training accumulator. Current test windows become
                # training data only for later cutoffs, which is intended.
                for beta in BETAS:
                    train_loss[beta] += beta_loss(q, sc, actual, beta)
                train_n += 1

                si = split_for_date(rd)
                if si is not None and selected[si] is not None:
                    adj = adjusted(q, sc, selected[si])
                    stat_add(split_stats[si], q, adj, actual)
                    stat_add(month_stats[rd.strftime("%Y-%m")], q, adj, actual)
                    stat_add(venue_stats[venue], q, adj, actual)

            print(f"BAO_M2ROB_MONTH_COVERAGE={key} complete:{mcomplete} motor_ready:{mready}", flush=True)
            cutoff = b - timedelta(days=1)
            if cutoff in CUTOFF_TO_SPLIT:
                si = CUTOFF_TO_SPLIT[cutoff]
                best = min(BETAS, key=lambda x: train_loss[x] / train_n)
                selected[si] = best
                top = sorted(BETAS, key=lambda x: train_loss[x] / train_n)[:5]
                print(
                    f"BAO_M2ROB_SELECT=split:{si+1} train_end:{cutoff} n:{train_n} beta:{best:.2f} top:"
                    + ",".join(f"{x:.2f}:{train_loss[x]/train_n:.6f}" for x in top),
                    flush=True,
                )
            cur = mx

    print(f"BAO_M2ROB_COVERAGE=total:{total} complete:{complete} motor_ready:{motor_ready}", flush=True)
    overall = stat_new()
    for i, (_, a, b) in enumerate(SPLITS):
        print(f"BAO_M2ROB_SPLIT={i+1} test:{a}..{b} beta:{selected[i]:.2f} {stat_fmt(split_stats[i])}", flush=True)
        stat_merge(overall, split_stats[i])

    neg_months = total_months = 0
    for key in sorted(month_stats):
        s = month_stats[key]
        if s["n"]:
            total_months += 1
            if s["diff_sum"] / s["n"] < 0:
                neg_months += 1
            print(f"BAO_M2ROB_MONTH={key} {stat_fmt(s)}", flush=True)

    neg_venues = total_venues = 0
    for venue in sorted(venue_stats):
        s = venue_stats[venue]
        if s["n"] >= 500:
            total_venues += 1
            if s["diff_sum"] / s["n"] < 0:
                neg_venues += 1
            print(f"BAO_M2ROB_VENUE={venue} {stat_fmt(s)}", flush=True)

    print("BAO_M2ROB_SELECTED_BETAS=" + ",".join(f"{x:.2f}" for x in selected), flush=True)
    print(f"BAO_M2ROB_STABILITY=negative_delta_months:{neg_months}/{total_months} negative_delta_venues_n500:{neg_venues}/{total_venues}", flush=True)
    print("BAO_M2ROB_ALL=" + stat_fmt(overall), flush=True)

    n = overall["n"]
    dll = overall["diff_sum"] / n if n else 0.0
    if n > 1:
        var = max(0.0, (overall["diff_sq"] - overall["diff_sum"] ** 2 / n) / (n - 1))
        se = math.sqrt(var / n)
    else:
        se = 0.0
    robust = (
        n > 0
        and dll < 0
        and all(x is not None and x > 0 for x in selected)
        and neg_months >= max(6, total_months - 2)
        and (se == 0.0 or dll / se <= -2.0)
    )
    print("BAO_M2ROB_VERDICT=" + ("ROBUST_CANDIDATE" if robust else "NOT_YET_ROBUST"), flush=True)
    print("BAO_M2ROB_POLICY=no_production_change", flush=True)
    print("BAO_M2ROB_NEXT=if_robust_build_forward_early_market_plus_motor2_shadow_then_compare_actionable_late_odds", flush=True)
    print("BAO_M2ROB_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
