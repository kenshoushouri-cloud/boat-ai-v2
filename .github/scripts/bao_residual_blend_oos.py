# -*- coding: utf-8 -*-
"""Train-only OOS diagnostic for model information beyond the market.

For each complete 120-ticket race:
  q = de-vigged historical market probability
  p = odds-independent v24 probability using PROB_TEMP=1.20
  r_alpha ∝ q * (p/q)^alpha = q^(1-alpha) * p^alpha

alpha=0 is market-only; alpha=1 is model-only.  Alpha is selected on prior
races using multiclass log loss, then frozen into the future test window.
This is research-only: historical odds are not proven actionable timestamps.
No DB writes or prediction persistence occur.
"""
from __future__ import annotations

import math
import os
import re
from collections import defaultdict
from datetime import date, timedelta

import psycopg
from psycopg.rows import dict_row

import v24_pre_candidate_notifier_pg as v24

DB = os.getenv("DATABASE_URL", "").strip()
START = date.fromisoformat("2025-07-01")
END = date.fromisoformat("2026-08-22")
TEMP = 1.20
ALPHAS = [0.00, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.75, 1.00]
SPLITS = [
    (date(2025, 12, 31), date(2026, 1, 1), date(2026, 2, 28)),
    (date(2026, 2, 28), date(2026, 3, 1), date(2026, 4, 30)),
    (date(2026, 4, 30), date(2026, 5, 1), date(2026, 6, 30)),
    (date(2026, 6, 30), date(2026, 7, 1), END),
]
EPS = 1e-15


def nt(v):
    x = re.findall(r"[1-6]", str(v or ""))
    return "-".join(x[:3]) if len(x) >= 3 else str(v or "").strip()


def nextm(d):
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def probs_at_temp(entries, venue, temp):
    by = v24._entry_by_lane(entries)
    raw = {i: v24._lane_raw_strength(by[i], i, venue) for i in range(1, 7)}
    w = {i: math.exp(raw[i] / temp) for i in range(1, 7)}
    tot = sum(w.values())
    out = {}
    for a in range(1, 7):
        pa = w[a] / tot
        tb = tot - w[a]
        for b in range(1, 7):
            if b == a:
                continue
            pb = w[b] / tb
            tc = tb - w[b]
            for c in range(1, 7):
                if c == a or c == b:
                    continue
                out[f"{a}-{b}-{c}"] = pa * pb * (w[c] / tc)
    return out


def empty_metric():
    return {"n": 0, "logloss": 0.0, "brier": 0.0, "rank": 0.0}


def add_metric(m, probs, actual):
    pa = max(float(probs[actual]), EPS)
    brier = 1.0 - 2.0 * pa + sum(float(x) * float(x) for x in probs.values())
    rank = 1 + sum(1 for x in probs.values() if float(x) > pa)
    m["n"] += 1
    m["logloss"] += -math.log(pa)
    m["brier"] += brier
    m["rank"] += rank


def merge_metric(dst, src):
    for k in ("n", "logloss", "brier", "rank"):
        dst[k] += src[k]


def fm(m):
    n = m["n"]
    if not n:
        return "n:0 logloss:n/a brier:n/a mean_rank:n/a"
    return (
        f"n:{n} logloss:{m['logloss']/n:.6f} "
        f"brier:{m['brier']/n:.6f} mean_rank:{m['rank']/n:.2f}"
    )


def blend(p, q, alpha):
    # Stable geometric residual blend in log space.
    logs = {}
    mx = -1e100
    for t in p:
        lp = math.log(max(float(p[t]), EPS))
        lq = math.log(max(float(q[t]), EPS))
        z = (1.0 - alpha) * lq + alpha * lp
        logs[t] = z
        if z > mx:
            mx = z
    vals = {t: math.exp(z - mx) for t, z in logs.items()}
    s = sum(vals.values())
    return {t: v / s for t, v in vals.items()}


def main():
    if not DB:
        raise RuntimeError("DATABASE_URL is required")

    print(
        f"BAO_RESID_MODE=read_only_train_only temp:{TEMP:.2f} period:{START}..{END}",
        flush=True,
    )
    print("BAO_RESID_FORMULA=r_alpha~q*(p/q)^alpha", flush=True)
    print("BAO_RESID_ALPHA_GRID=" + ",".join(f"{a:.2f}" for a in ALPHAS), flush=True)
    print("BAO_RESID_ODDS_CAVEAT=historical_price_not_proven_actionable_timestamp", flush=True)

    stats = []
    for _ in SPLITS:
        stats.append(
            {
                "train": {a: empty_metric() for a in ALPHAS},
                "test": {a: empty_metric() for a in ALPHAS},
            }
        )

    monthly = defaultdict(lambda: {"races": 0, "complete": 0})
    total_races = 0
    complete_races = 0

    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        cur = date(START.year, START.month, 1)
        while cur <= END:
            mx = nextm(cur)
            a = max(START, cur)
            b = min(END + timedelta(days=1), mx)
            key = a.strftime("%Y-%m")

            with conn.cursor() as c:
                c.execute("set statement_timeout='120s'")
                c.execute(
                    """select r.race_id,r.race_date,coalesce(r.venue_id,r.venue_code) venue_id
                       from v2_races r
                       where r.race_date >= %s and r.race_date < %s
                       order by r.race_id""",
                    (a, b),
                )
                races = [dict(x) for x in c.fetchall()]
                c.execute(
                    """select e.race_id,e.lane,e.racer_number,e.racer_class,e.racer_name,
                              e.national_win_rate,e.national_place2_rate,e.local_win_rate,
                              e.local_place2_rate,e.avg_st,e.motor_no,e.boat_no
                       from v2_race_entries e
                       join v2_races r on r.race_id=e.race_id
                       where r.race_date >= %s and r.race_date < %s
                       order by e.race_id,e.lane""",
                    (a, b),
                )
                ents = [dict(x) for x in c.fetchall()]
                c.execute(
                    """select o.race_id,o.ticket,o.odds
                       from v2_odds_trifecta o
                       join v2_races r on r.race_id=o.race_id
                       where r.race_date >= %s and r.race_date < %s
                         and o.odds is not null and o.odds > 1
                       order by o.race_id,o.ticket""",
                    (a, b),
                )
                odds = [dict(x) for x in c.fetchall()]
                c.execute(
                    """select res.race_id,res.trifecta_ticket
                       from v2_results res
                       join v2_races r on r.race_id=res.race_id
                       where r.race_date >= %s and r.race_date < %s""",
                    (a, b),
                )
                results = {str(x["race_id"]): nt(x["trifecta_ticket"]) for x in c.fetchall()}

            eb = defaultdict(list)
            for e in ents:
                eb[str(e["race_id"])].append(e)
            ob = defaultdict(dict)
            for o in odds:
                rid = str(o["race_id"])
                t = nt(o["ticket"])
                if t:
                    ob[rid][t] = float(o["odds"])

            total_races += len(races)
            monthly[key]["races"] += len(races)

            for r in races:
                rid = str(r["race_id"])
                rd = r["race_date"]
                es = eb.get(rid, [])
                om = ob.get(rid, {})
                actual = results.get(rid, "")
                if len(es) != 6 or {int(x.get("lane") or 0) for x in es} != {1, 2, 3, 4, 5, 6}:
                    continue
                if len(om) != 120 or actual not in om:
                    continue
                try:
                    p = probs_at_temp(es, str(r.get("venue_id") or "").zfill(2), TEMP)
                except Exception:
                    continue
                if len(p) != 120 or actual not in p or abs(sum(p.values()) - 1.0) > 1e-10:
                    continue
                inv = {t: 1.0 / float(odd) for t, odd in om.items() if t in p and odd > 1.0}
                if len(inv) != 120:
                    continue
                si = sum(inv.values())
                q = {t: v / si for t, v in inv.items()}

                complete_races += 1
                monthly[key]["complete"] += 1
                blended = {alpha: blend(p, q, alpha) for alpha in ALPHAS}

                for i, (train_end, test_start, test_end) in enumerate(SPLITS):
                    bucket = None
                    if START <= rd <= train_end:
                        bucket = "train"
                    elif test_start <= rd <= test_end:
                        bucket = "test"
                    if bucket:
                        for alpha in ALPHAS:
                            add_metric(stats[i][bucket][alpha], blended[alpha], actual)

            print(
                f"BAO_RESID_MONTH={key} races:{monthly[key]['races']} complete:{monthly[key]['complete']}",
                flush=True,
            )
            cur = mx

    print(f"BAO_RESID_COVERAGE=complete:{complete_races}/{total_races}", flush=True)

    combined_selected = empty_metric()
    combined_market = empty_metric()
    combined_model = empty_metric()
    selected_alphas = []

    for i, (train_end, test_start, test_end) in enumerate(SPLITS, 1):
        train = stats[i - 1]["train"]
        test = stats[i - 1]["test"]
        valid = [a for a in ALPHAS if train[a]["n"] > 0]
        if not valid:
            raise RuntimeError(f"split {i}: no train rows")
        selected = min(valid, key=lambda x: train[x]["logloss"] / train[x]["n"])
        selected_alphas.append(selected)
        top = sorted(valid, key=lambda x: train[x]["logloss"] / train[x]["n"])[:5]
        print(
            f"BAO_RESID_SPLIT={i} train_end:{train_end} test:{test_start}..{test_end} selected_alpha:{selected:.2f}",
            flush=True,
        )
        print(
            "BAO_RESID_TRAIN_TOP=" + str(i) + " " + ",".join(
                f"{a:.2f}:{train[a]['logloss']/train[a]['n']:.6f}" for a in top
            ),
            flush=True,
        )
        print(f"BAO_RESID_TEST_MARKET={i} alpha:0.00 " + fm(test[0.00]), flush=True)
        print(f"BAO_RESID_TEST_SELECTED={i} alpha:{selected:.2f} " + fm(test[selected]), flush=True)
        print(f"BAO_RESID_TEST_MODEL={i} alpha:1.00 " + fm(test[1.00]), flush=True)
        if test[selected]["n"]:
            dm = test[selected]["logloss"] / test[selected]["n"] - test[0.00]["logloss"] / test[0.00]["n"]
            db = test[selected]["brier"] / test[selected]["n"] - test[0.00]["brier"] / test[0.00]["n"]
            dr = test[selected]["rank"] / test[selected]["n"] - test[0.00]["rank"] / test[0.00]["n"]
            print(
                f"BAO_RESID_TEST_DELTA={i} selected_minus_market logloss:{dm:.6f} brier:{db:.6f} rank:{dr:.2f}",
                flush=True,
            )
        merge_metric(combined_selected, test[selected])
        merge_metric(combined_market, test[0.00])
        merge_metric(combined_model, test[1.00])

    print("BAO_RESID_SELECTED_ALPHAS=" + ",".join(f"{x:.2f}" for x in selected_alphas), flush=True)
    print("BAO_RESID_ALL_MARKET=" + fm(combined_market), flush=True)
    print("BAO_RESID_ALL_SELECTED=" + fm(combined_selected), flush=True)
    print("BAO_RESID_ALL_MODEL=" + fm(combined_model), flush=True)
    if combined_selected["n"]:
        dm = combined_selected["logloss"] / combined_selected["n"] - combined_market["logloss"] / combined_market["n"]
        db = combined_selected["brier"] / combined_selected["n"] - combined_market["brier"] / combined_market["n"]
        dr = combined_selected["rank"] / combined_selected["n"] - combined_market["rank"] / combined_market["n"]
        print(
            f"BAO_RESID_ALL_DELTA=selected_minus_market logloss:{dm:.6f} brier:{db:.6f} rank:{dr:.2f}",
            flush=True,
        )
    print("BAO_RESID_POLICY=diagnostic_only_no_production_change", flush=True)
    print("BAO_RESID_NEXT=if_alpha_positive_and_oos_improves_test_feature_residuals_then_actionable_odds_forward", flush=True)
    print("BAO_RESID_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
