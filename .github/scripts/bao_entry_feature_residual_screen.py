# -*- coding: utf-8 -*-
"""Screen entry-level boat-racing features for incremental signal beyond market.

For each feature, six lane values are standardized within race. A ticket score
uses finish-position weights 1.0 / 0.6 / 0.3. The market probability q is then
adjusted only by that feature:
    r_beta(ticket) ∝ q(ticket) * exp(beta * feature_ticket_score)

beta is selected using prior-race multiclass log loss only and frozen into the
next two-month OOS window. No DB writes; historical odds are research evidence.
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
BETAS = [-0.30, -0.15, -0.05, 0.00, 0.05, 0.15, 0.30]
FEATURES = ("motor2", "avg_st", "local2", "nat_win", "nat2", "racer_class")
POS_W = (1.0, 0.6, 0.3)
EPS = 1e-15
SPLITS = [
    (date(2025, 12, 31), date(2026, 1, 1), date(2026, 2, 28)),
    (date(2026, 2, 28), date(2026, 3, 1), date(2026, 4, 30)),
    (date(2026, 4, 30), date(2026, 5, 1), date(2026, 6, 30)),
    (date(2026, 6, 30), date(2026, 7, 1), END),
]
CUTOFF_TO_SPLIT = {x[0]: i for i, x in enumerate(SPLITS)}


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


def feature_values(entries, name):
    by = {int(e.get("lane") or 0): e for e in entries}
    if set(by) != {1, 2, 3, 4, 5, 6}:
        return None
    vals = []
    for lane in range(1, 7):
        e = by[lane]
        if name == "motor2":
            x = sf(e.get("motor_place2_rate"))
            if x is None or not (0 <= x <= 100):
                return None
        elif name == "avg_st":
            x = sf(e.get("avg_st"))
            if x is None or not (0 < x < 1):
                return None
            x = -x  # higher score = better/faster ST
        elif name == "local2":
            x = sf(e.get("local_place2_rate"))
            if x is None or not (0 <= x <= 100):
                return None
        elif name == "nat_win":
            x = sf(e.get("national_win_rate"))
            if x is None or not (0 <= x <= 20):
                return None
        elif name == "nat2":
            x = sf(e.get("national_place2_rate"))
            if x is None or not (0 <= x <= 100):
                return None
        elif name == "racer_class":
            x = sf(e.get("racer_class"))
            if x is None or int(x) not in (1, 2, 3, 4):
                return None
        else:
            raise KeyError(name)
        vals.append(float(x))
    mu = sum(vals) / 6.0
    var = sum((x - mu) ** 2 for x in vals) / 6.0
    sd = math.sqrt(var)
    if sd < 1e-12:
        return None
    return {lane: (vals[lane - 1] - mu) / sd for lane in range(1, 7)}


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


def loss_for_beta(q, scores, actual, beta):
    if beta == 0.0:
        return -math.log(max(q[actual], EPS))
    den = 0.0
    for t, qq in q.items():
        den += qq * math.exp(beta * scores[t])
    pa = q[actual] * math.exp(beta * scores[actual]) / den
    return -math.log(max(pa, EPS))


def adjusted(q, scores, beta):
    if beta == 0.0:
        return dict(q)
    vals = {t: qq * math.exp(beta * scores[t]) for t, qq in q.items()}
    s = sum(vals.values())
    return {t: v / s for t, v in vals.items()}


def metric_new():
    return {"n": 0, "ll": 0.0, "br": 0.0, "rank": 0.0}


def metric_add(m, probs, actual):
    pa = max(probs[actual], EPS)
    m["n"] += 1
    m["ll"] += -math.log(pa)
    m["br"] += 1.0 - 2.0 * pa + sum(x * x for x in probs.values())
    m["rank"] += 1 + sum(1 for x in probs.values() if x > pa)


def metric_merge(a, b):
    for k in a:
        a[k] += b[k]


def fmt(m):
    n = m["n"]
    if not n:
        return "n:0 logloss:n/a brier:n/a mean_rank:n/a"
    return f"n:{n} logloss:{m['ll']/n:.6f} brier:{m['br']/n:.6f} mean_rank:{m['rank']/n:.2f}"


def active_split(rd):
    for i, (_, a, b) in enumerate(SPLITS):
        if a <= rd <= b:
            return i
    return None


def main():
    if not DB:
        raise RuntimeError("DATABASE_URL is required")
    print(f"BAO_FEAT_MODE=read_only_market_residual period:{START}..{END}", flush=True)
    print("BAO_FEAT_FEATURES=" + ",".join(FEATURES), flush=True)
    print("BAO_FEAT_BETA_GRID=" + ",".join(f"{x:.2f}" for x in BETAS), flush=True)
    print("BAO_FEAT_FORMULA=r_beta~q*exp(beta*feature_ticket_score)", flush=True)

    train_ll = {f: {b: 0.0 for b in BETAS} for f in FEATURES}
    train_n = {f: 0 for f in FEATURES}
    selected = [dict() for _ in SPLITS]
    test_adj = [{f: metric_new() for f in FEATURES} for _ in SPLITS]
    test_mkt = [{f: metric_new() for f in FEATURES} for _ in SPLITS]
    coverage = {f: 0 for f in FEATURES}
    base_complete = 0
    total_races = 0

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        cur = date(START.year, START.month, 1)
        while cur <= END:
            mx = nextm(cur)
            a = max(START, cur)
            b = min(END + timedelta(days=1), mx)
            key = a.strftime("%Y-%m")
            with conn.cursor() as c:
                c.execute("set statement_timeout='120s'")
                c.execute("""select race_id,race_date from v2_races where race_date >= %s and race_date < %s order by race_id""", (a, b))
                races = [dict(x) for x in c.fetchall()]
                c.execute("""select e.race_id,e.lane,e.racer_class,e.national_win_rate,e.national_place2_rate,
                                     e.local_place2_rate,e.avg_st,e.motor_place2_rate
                              from v2_race_entries e join v2_races r on r.race_id=e.race_id
                              where r.race_date >= %s and r.race_date < %s order by e.race_id,e.lane""", (a, b))
                entries = [dict(x) for x in c.fetchall()]
                c.execute("""select o.race_id,o.ticket,o.odds from v2_odds_trifecta o
                              join v2_races r on r.race_id=o.race_id
                              where r.race_date >= %s and r.race_date < %s and o.odds > 1
                              order by o.race_id,o.ticket""", (a, b))
                odds = [dict(x) for x in c.fetchall()]
                c.execute("""select res.race_id,res.trifecta_ticket from v2_results res
                              join v2_races r on r.race_id=res.race_id
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

            month_complete = 0
            month_cov = {f: 0 for f in FEATURES}
            total_races += len(races)
            for r in races:
                rid = str(r["race_id"])
                rd = r["race_date"]
                es = eb.get(rid, [])
                om = ob.get(rid, {})
                actual = results.get(rid, "")
                if len(es) != 6 or len(om) != 120 or actual not in om:
                    continue
                inv = {t: 1.0 / odd for t, odd in om.items() if odd > 1.0}
                if len(inv) != 120:
                    continue
                s = sum(inv.values())
                q = {t: v / s for t, v in inv.items()}
                if actual not in q:
                    continue
                base_complete += 1
                month_complete += 1
                si = active_split(rd)

                for f in FEATURES:
                    z = feature_values(es, f)
                    if z is None:
                        continue
                    coverage[f] += 1
                    month_cov[f] += 1
                    sc = ticket_scores(z)

                    # Expanding train: every past race contributes to future cutoffs.
                    for beta in BETAS:
                        train_ll[f][beta] += loss_for_beta(q, sc, actual, beta)
                    train_n[f] += 1

                    # Evaluate only with beta frozen at the previous cutoff.
                    if si is not None and f in selected[si]:
                        beta = selected[si][f]
                        metric_add(test_mkt[si][f], q, actual)
                        metric_add(test_adj[si][f], adjusted(q, sc, beta), actual)

            print(
                f"BAO_FEAT_MONTH={key} complete:{month_complete} "
                + " ".join(f"{f}:{month_cov[f]}" for f in FEATURES),
                flush=True,
            )

            cutoff = b - timedelta(days=1)
            if cutoff in CUTOFF_TO_SPLIT:
                si = CUTOFF_TO_SPLIT[cutoff]
                for f in FEATURES:
                    n = train_n[f]
                    if not n:
                        continue
                    best = min(BETAS, key=lambda beta: train_ll[f][beta] / n)
                    selected[si][f] = best
                    top = sorted(BETAS, key=lambda beta: train_ll[f][beta] / n)[:3]
                    print(
                        f"BAO_FEAT_SELECT=split:{si+1} train_end:{cutoff} feature:{f} beta:{best:.2f} "
                        + "top:" + ",".join(f"{x:.2f}:{train_ll[f][x]/n:.6f}" for x in top),
                        flush=True,
                    )
            cur = mx

    print(f"BAO_FEAT_BASE_COMPLETE={base_complete}/{total_races}", flush=True)
    for f in FEATURES:
        print(f"BAO_FEAT_COVERAGE={f} {coverage[f]}/{base_complete}", flush=True)

    combined_adj = {f: metric_new() for f in FEATURES}
    combined_mkt = {f: metric_new() for f in FEATURES}
    good_splits = {f: 0 for f in FEATURES}
    nonzero_splits = {f: 0 for f in FEATURES}

    for si, (_, ta, tb) in enumerate(SPLITS):
        for f in FEATURES:
            if f not in selected[si]:
                continue
            beta = selected[si][f]
            ma = test_mkt[si][f]
            aa = test_adj[si][f]
            if not aa["n"]:
                continue
            dll = aa["ll"] / aa["n"] - ma["ll"] / ma["n"]
            dbr = aa["br"] / aa["n"] - ma["br"] / ma["n"]
            dr = aa["rank"] / aa["n"] - ma["rank"] / ma["n"]
            if beta != 0.0:
                nonzero_splits[f] += 1
            if dll < 0:
                good_splits[f] += 1
            print(f"BAO_FEAT_TEST=split:{si+1} test:{ta}..{tb} feature:{f} beta:{beta:.2f} market:[{fmt(ma)}] adjusted:[{fmt(aa)}] delta_ll:{dll:.6f} delta_brier:{dbr:.6f} delta_rank:{dr:.2f}", flush=True)
            metric_merge(combined_mkt[f], ma)
            metric_merge(combined_adj[f], aa)

    for f in FEATURES:
        ma = combined_mkt[f]
        aa = combined_adj[f]
        if not aa["n"]:
            continue
        dll = aa["ll"] / aa["n"] - ma["ll"] / ma["n"]
        dbr = aa["br"] / aa["n"] - ma["br"] / ma["n"]
        dr = aa["rank"] / aa["n"] - ma["rank"] / ma["n"]
        verdict = "CANDIDATE" if dll < 0 and good_splits[f] >= 3 and nonzero_splits[f] >= 3 else "NO_STABLE_INCREMENT"
        print(f"BAO_FEAT_ALL=feature:{f} market:[{fmt(ma)}] adjusted:[{fmt(aa)}] delta_ll:{dll:.6f} delta_brier:{dbr:.6f} delta_rank:{dr:.2f} good_splits:{good_splits[f]} nonzero_splits:{nonzero_splits[f]} verdict:{verdict}", flush=True)

    print("BAO_FEAT_POLICY=screen_only_no_production_change", flush=True)
    print("BAO_FEAT_NEXT=promote_only_stable_candidates_to_multifeature_train_only_residual_model", flush=True)
    print("BAO_FEAT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
