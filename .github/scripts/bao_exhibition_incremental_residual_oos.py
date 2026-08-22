# -*- coding: utf-8 -*-
"""Read-only OOS audit: do exhibition signals add value beyond market + Motor2?

The de-vigged 120-ticket market probability is the baseline.  Motor2 uses the
split-specific train-only coefficients already validated in PR #108.  For each
future split, an additional exhibition coefficient is selected using prior
races only and frozen into the future test window.

No DB writes, persistence, Production, Shadow, or LINE changes.
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
HIST = "historical"
EPS = 1e-15
POS_W = (1.0, 0.6, 0.3)
EXTRA_BETAS = (-0.15, -0.05, 0.0, 0.05, 0.15)
FEATURES = ("ex_time", "ex_st")
SPLITS = [
    (date(2025, 12, 31), date(2026, 1, 1), date(2026, 2, 28), 0.08),
    (date(2026, 2, 28), date(2026, 3, 1), date(2026, 4, 30), 0.08),
    (date(2026, 4, 30), date(2026, 5, 1), date(2026, 6, 30), 0.08),
    (date(2026, 6, 30), date(2026, 7, 1), END, 0.06),
]
CUTOFF_TO_SPLIT = {x[0]: i for i, x in enumerate(SPLITS)}
UNIQUE_MOTOR_BETAS = sorted({x[3] for x in SPLITS})


def nt(v):
    xs = re.findall(r"[1-6]", str(v or ""))
    return "-".join(xs[:3]) if len(xs) >= 3 else ""


def nextm(d):
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def sf(v):
    try:
        return None if v is None or v == "" else float(v)
    except Exception:
        return None


def zscore(vals):
    if len(vals) != 6:
        return None
    mu = sum(vals) / 6.0
    var = sum((x - mu) ** 2 for x in vals) / 6.0
    sd = math.sqrt(var)
    if sd < 1e-12:
        return None
    return {i + 1: (vals[i] - mu) / sd for i in range(6)}


def lane_features(entries, exhibition):
    eb = {int(x.get("lane") or 0): x for x in entries}
    xb = {int(x.get("lane") or 0): x for x in exhibition}
    if set(eb) != {1, 2, 3, 4, 5, 6} or set(xb) != {1, 2, 3, 4, 5, 6}:
        return None
    motor = []
    ex_time = []
    ex_st = []
    for lane in range(1, 7):
        m = sf(eb[lane].get("motor_place2_rate"))
        tr = sf(xb[lane].get("exhibition_time_rank"))
        sr = sf(xb[lane].get("start_timing_rank"))
        if m is None or not (0 <= m <= 100):
            return None
        if tr is None or int(tr) not in range(1, 7):
            return None
        if sr is None or int(sr) not in range(1, 7):
            return None
        motor.append(m)
        ex_time.append(-tr)  # higher score = better rank
        ex_st.append(-sr)
    zm, zt, zs = zscore(motor), zscore(ex_time), zscore(ex_st)
    if not zm or not zt or not zs:
        return None
    return {"motor": zm, "ex_time": zt, "ex_st": zs}


def ticket_scores(z):
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


def loss(q, sm, sx, actual, bm, bx):
    den = 0.0
    num = 0.0
    for t, qq in q.items():
        v = qq * math.exp(bm * sm[t] + bx * sx[t])
        den += v
        if t == actual:
            num = v
    return -math.log(max(num / den, EPS))


def adjusted(q, sm, sx, bm, bx):
    vals = {t: qq * math.exp(bm * sm[t] + bx * sx[t]) for t, qq in q.items()}
    s = sum(vals.values())
    return {t: v / s for t, v in vals.items()}


def metric_new():
    return {"n": 0, "ll": 0.0, "br": 0.0, "rank": 0.0}


def metric_add(m, p, actual):
    pa = max(p[actual], EPS)
    m["n"] += 1
    m["ll"] += -math.log(pa)
    m["br"] += 1.0 - 2.0 * pa + sum(x * x for x in p.values())
    m["rank"] += 1 + sum(1 for x in p.values() if x > pa)


def metric_merge(a, b):
    for k in a:
        a[k] += b[k]


def fmt(m):
    n = m["n"]
    if not n:
        return "n:0 logloss:n/a brier:n/a rank:n/a"
    return f"n:{n} logloss:{m['ll']/n:.6f} brier:{m['br']/n:.6f} rank:{m['rank']/n:.2f}"


def active_split(rd):
    for i, (_, a, b, _) in enumerate(SPLITS):
        if a <= rd <= b:
            return i
    return None


def main():
    if not DB:
        raise RuntimeError("DATABASE_URL is required")
    print(f"BAO_EXINC_MODE=read_only period:{START}..{END} label:{HIST}", flush=True)
    print("BAO_EXINC_BASELINE=devig_market_plus_train_only_motor2_from_pr108", flush=True)
    print("BAO_EXINC_FEATURES=exhibition_time_rank,start_timing_rank", flush=True)
    print("BAO_EXINC_POLICY=no_writes_no_production_no_shadow_no_line", flush=True)

    # cumulative train losses for each prevalidated Motor2 beta and extra beta.
    train_loss = {
        f: {bm: {bx: 0.0 for bx in EXTRA_BETAS} for bm in UNIQUE_MOTOR_BETAS}
        for f in FEATURES
    }
    train_n = {f: {bm: 0 for bm in UNIQUE_MOTOR_BETAS} for f in FEATURES}
    selected = [dict() for _ in SPLITS]
    test_market = [{f: metric_new() for f in FEATURES} for _ in SPLITS]
    test_motor = [{f: metric_new() for f in FEATURES} for _ in SPLITS]
    test_joint = [{f: metric_new() for f in FEATURES} for _ in SPLITS]
    complete = 0
    total = 0

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        curm = date(START.year, START.month, 1)
        while curm <= END:
            nxt = nextm(curm)
            a, b = max(curm, START), min(nxt, END + timedelta(days=1))
            with conn.cursor() as c:
                c.execute("set statement_timeout='180s'")
                c.execute("select race_id,race_date from v2_races where race_date >= %s and race_date < %s order by race_id", (a, b))
                races = [dict(x) for x in c.fetchall()]
                c.execute("""select e.race_id,e.lane,e.motor_place2_rate
                             from v2_race_entries e join v2_races r on r.race_id=e.race_id
                             where r.race_date >= %s and r.race_date < %s order by e.race_id,e.lane""", (a, b))
                entries = [dict(x) for x in c.fetchall()]
                c.execute("""select x.race_id,x.lane,x.exhibition_time_rank,x.start_timing_rank
                             from v2_realtime_exhibition_snapshots x join v2_races r on r.race_id=x.race_id
                             where r.race_date >= %s and r.race_date < %s and x.snapshot_label=%s
                             order by x.race_id,x.lane""", (a, b, HIST))
                exhibition = [dict(x) for x in c.fetchall()]
                c.execute("""select o.race_id,o.ticket,o.odds from v2_odds_trifecta o join v2_races r on r.race_id=o.race_id
                             where r.race_date >= %s and r.race_date < %s and o.odds > 1 order by o.race_id,o.ticket""", (a, b))
                odds = [dict(x) for x in c.fetchall()]
                c.execute("""select res.race_id,res.trifecta_ticket from v2_results res join v2_races r on r.race_id=res.race_id
                             where r.race_date >= %s and r.race_date < %s""", (a, b))
                results = {str(x["race_id"]): nt(x["trifecta_ticket"]) for x in c.fetchall()}

            eb, xb, ob = defaultdict(list), defaultdict(list), defaultdict(dict)
            for x in entries: eb[str(x["race_id"])].append(x)
            for x in exhibition: xb[str(x["race_id"])].append(x)
            for x in odds:
                t = nt(x["ticket"])
                if t: ob[str(x["race_id"])][t] = float(x["odds"])

            month_ok = 0
            total += len(races)
            for r in races:
                rid, rd = str(r["race_id"]), r["race_date"]
                om = ob.get(rid, {})
                actual = results.get(rid, "")
                feats = lane_features(eb.get(rid, []), xb.get(rid, []))
                if feats is None or len(om) != 120 or actual not in om:
                    continue
                inv = {t: 1.0 / o for t, o in om.items() if o > 1.0}
                if len(inv) != 120:
                    continue
                den = sum(inv.values())
                q = {t: v / den for t, v in inv.items()}
                sm = ticket_scores(feats["motor"])
                sx = {f: ticket_scores(feats[f]) for f in FEATURES}
                complete += 1; month_ok += 1

                # Accumulate train evidence for both Motor2 coefficients used by #108.
                for bm in UNIQUE_MOTOR_BETAS:
                    for f in FEATURES:
                        for bx in EXTRA_BETAS:
                            train_loss[f][bm][bx] += loss(q, sm, sx[f], actual, bm, bx)
                        train_n[f][bm] += 1

                si = active_split(rd)
                if si is not None and FEATURES[0] in selected[si]:
                    bm = SPLITS[si][3]
                    for f in FEATURES:
                        bx = selected[si][f]
                        metric_add(test_market[si][f], q, actual)
                        metric_add(test_motor[si][f], adjusted(q, sm, sx[f], bm, 0.0), actual)
                        metric_add(test_joint[si][f], adjusted(q, sm, sx[f], bm, bx), actual)

            print(f"BAO_EXINC_MONTH={a.strftime('%Y-%m')} complete:{month_ok}/{len(races)}", flush=True)
            cutoff = b - timedelta(days=1)
            if cutoff in CUTOFF_TO_SPLIT:
                si = CUTOFF_TO_SPLIT[cutoff]
                bm = SPLITS[si][3]
                for f in FEATURES:
                    n = train_n[f][bm]
                    best = min(EXTRA_BETAS, key=lambda bx: train_loss[f][bm][bx] / max(n, 1))
                    selected[si][f] = best
                    top = sorted(EXTRA_BETAS, key=lambda bx: train_loss[f][bm][bx] / max(n, 1))[:3]
                    print(f"BAO_EXINC_SELECT=split:{si+1} train_end:{cutoff} feature:{f} motor_beta:{bm:.2f} extra_beta:{best:.2f} n:{n} top:" + ",".join(f"{x:.2f}:{train_loss[f][bm][x]/max(n,1):.6f}" for x in top), flush=True)
            curm = nxt

    print(f"BAO_EXINC_COVERAGE={complete}/{total}", flush=True)
    all_motor = {f: metric_new() for f in FEATURES}
    all_joint = {f: metric_new() for f in FEATURES}
    good = {f: 0 for f in FEATURES}
    nonzero = {f: 0 for f in FEATURES}
    for si, (_, ta, tb, bm) in enumerate(SPLITS):
        for f in FEATURES:
            m, j = test_motor[si][f], test_joint[si][f]
            if not j["n"]: continue
            dll = j["ll"] / j["n"] - m["ll"] / m["n"]
            dbr = j["br"] / j["n"] - m["br"] / m["n"]
            dr = j["rank"] / j["n"] - m["rank"] / m["n"]
            bx = selected[si][f]
            good[f] += int(dll < 0)
            nonzero[f] += int(bx != 0.0)
            print(f"BAO_EXINC_TEST=split:{si+1} test:{ta}..{tb} feature:{f} motor_beta:{bm:.2f} extra_beta:{bx:.2f} motor:[{fmt(m)}] joint:[{fmt(j)}] delta_ll:{dll:.6f} delta_brier:{dbr:.6f} delta_rank:{dr:.2f}", flush=True)
            metric_merge(all_motor[f], m); metric_merge(all_joint[f], j)

    for f in FEATURES:
        m, j = all_motor[f], all_joint[f]
        if not j["n"]: continue
        dll = j["ll"] / j["n"] - m["ll"] / m["n"]
        dbr = j["br"] / j["n"] - m["br"] / m["n"]
        dr = j["rank"] / j["n"] - m["rank"] / m["n"]
        verdict = "CANDIDATE_INCREMENT" if dll < 0 and good[f] >= 3 and nonzero[f] >= 3 else "NO_STABLE_INCREMENT"
        print(f"BAO_EXINC_ALL=feature:{f} motor:[{fmt(m)}] joint:[{fmt(j)}] delta_ll:{dll:.6f} delta_brier:{dbr:.6f} delta_rank:{dr:.2f} good_splits:{good[f]} nonzero_splits:{nonzero[f]} verdict:{verdict}", flush=True)

    print("BAO_EXINC_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
