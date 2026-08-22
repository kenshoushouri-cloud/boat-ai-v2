# -*- coding: utf-8 -*-
"""Train-only expanding OOS audit for wind-speed residual beyond market+Motor2+exhibition.

Reuses the already-reviewed market/Motor2/exhibition scoring utilities from
bao_wave_residual_oos.py, but builds a distinct venue x lane x wind-speed
profile. Read-only: no DB writes, Production, Shadow or LINE changes.
"""
from __future__ import annotations

import importlib.util
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

_HELPER = Path(__file__).with_name("bao_wave_residual_oos.py")
_spec = importlib.util.spec_from_file_location("bao_wave_residual_oos_helper", _HELPER)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load bao_wave_residual_oos helper")
W = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(W)


def wind_bucket(v: float) -> str:
    x = float(v)
    if x < 2:
        return "<2"
    if x < 4:
        return "2-<4"
    if x < 6:
        return "4-<6"
    return "6+"


def build_profile(conn, cutoff):
    q = """
    with b as (
      select r.venue_id,e.lane,w.wind_speed_m,
             case when re.finish_position=1 then 1 else 0 end win
      from v2_races r
      join v2_race_entries e using(race_id)
      join v2_result_entries re on re.race_id=e.race_id and re.lane=e.lane
      join v2_realtime_weather_snapshots w
        on w.race_id=r.race_id and w.snapshot_label=%s
      where r.race_date between %s and %s
        and re.finish_position between 1 and 6
        and w.wind_speed_m is not null
    )
    select venue_id,lane,
      case when wind_speed_m<2 then '<2'
           when wind_speed_m<4 then '2-<4'
           when wind_speed_m<6 then '4-<6'
           else '6+' end bucket,
      count(*) n,sum(win) wins
    from b group by venue_id,lane,3
    """
    with conn.cursor() as c:
        c.execute(q, (W.HIST, W.START, cutoff))
        rows = [dict(x) for x in c.fetchall()]
    base = defaultdict(lambda: [0, 0])
    for x in rows:
        key = (str(x["venue_id"]).zfill(2), int(x["lane"]))
        base[key][0] += int(x["n"])
        base[key][1] += int(x["wins"])
    out = {}
    for x in rows:
        venue = str(x["venue_id"]).zfill(2)
        lane = int(x["lane"])
        n = int(x["n"])
        wins = int(x["wins"])
        bn, bwins = base[(venue, lane)]
        if n < W.MIN_BUCKET or bn < W.MIN_BASE:
            continue
        pb = (wins + 0.5) / (n + 1.0)
        p0 = (bwins + 0.5) / (bn + 1.0)
        out[(venue, lane, str(x["bucket"]))] = (
            (W.logit(pb) - W.logit(p0)) * (n / (n + W.SHRINK_K))
        )
    return out


def rows_for_month(conn, a, b):
    with conn.cursor() as c:
        c.execute("set statement_timeout='180s'")
        c.execute(
            "select race_id,race_date,coalesce(venue_id,venue_code) venue_id "
            "from v2_races where race_date>=%s and race_date<%s order by race_id",
            (a, b),
        )
        races = [dict(x) for x in c.fetchall()]
        c.execute(
            """select e.race_id,e.lane,e.motor_place2_rate
               from v2_race_entries e join v2_races r using(race_id)
               where r.race_date>=%s and r.race_date<%s
               order by e.race_id,e.lane""",
            (a, b),
        )
        er = [dict(x) for x in c.fetchall()]
        c.execute(
            """select x.race_id,x.lane,x.exhibition_time_rank
               from v2_realtime_exhibition_snapshots x join v2_races r using(race_id)
               where r.race_date>=%s and r.race_date<%s and x.snapshot_label=%s
               order by x.race_id,x.lane""",
            (a, b, W.HIST),
        )
        xr = [dict(x) for x in c.fetchall()]
        c.execute(
            """select w.race_id,w.wind_speed_m
               from v2_realtime_weather_snapshots w join v2_races r using(race_id)
               where r.race_date>=%s and r.race_date<%s and w.snapshot_label=%s""",
            (a, b, W.HIST),
        )
        weather = {str(x["race_id"]): W.sf(x["wind_speed_m"]) for x in c.fetchall()}
        c.execute(
            """select o.race_id,o.ticket,o.odds
               from v2_odds_trifecta o join v2_races r using(race_id)
               where r.race_date>=%s and r.race_date<%s and o.odds>1
               order by o.race_id,o.ticket""",
            (a, b),
        )
        oo = [dict(x) for x in c.fetchall()]
        c.execute(
            """select res.race_id,res.trifecta_ticket
               from v2_results res join v2_races r using(race_id)
               where r.race_date>=%s and r.race_date<%s""",
            (a, b),
        )
        rr = {str(x["race_id"]): W.nt(x["trifecta_ticket"]) for x in c.fetchall()}
    eb = defaultdict(list)
    xb = defaultdict(list)
    ob = defaultdict(dict)
    for x in er:
        eb[str(x["race_id"])].append(x)
    for x in xr:
        xb[str(x["race_id"])].append(x)
    for x in oo:
        ticket = W.nt(x["ticket"])
        if ticket:
            ob[str(x["race_id"])][ticket] = float(x["odds"])
    return races, eb, xb, weather, ob, rr


def main():
    if not W.DB:
        raise RuntimeError("DATABASE_URL is required")
    print("BAO_WIND_OOS_MODE=read_only", flush=True)
    print("BAO_WIND_OOS_BASELINE=devig_market_plus_motor2_plus_exhibition", flush=True)
    months = defaultdict(W.stat_new)
    overall = W.stat_new()
    selected = []
    with psycopg.connect(W.DB, row_factory=dict_row, autocommit=True) as conn:
        for si, (cut, ta, tb, bm, bx) in enumerate(W.SPLITS, 1):
            profile = build_profile(conn, cut)
            losses = {weight: 0.0 for weight in W.WGRID}
            train_n = 0
            test = W.stat_new()
            print(
                f"BAO_WIND_PROFILE=split:{si} groups:{len(profile)} train_end:{cut}",
                flush=True,
            )
            cur = date(W.START.year, W.START.month, 1)
            while cur <= tb:
                mx = W.nextm(cur)
                a = max(cur, W.START)
                b = min(mx, tb + timedelta(days=1))
                races, eb, xb, weather, ob, rr = rows_for_month(conn, a, b)
                for r in races:
                    d = r["race_date"]
                    rid = str(r["race_id"])
                    actual = rr.get(rid, "")
                    wind = weather.get(rid)
                    om = ob.get(rid, {})
                    sc = W.entry_scores(eb.get(rid, []), xb.get(rid, []))
                    if wind is None or sc is None or len(om) != 120 or actual not in om:
                        continue
                    inv = {t: 1.0 / odds for t, odds in om.items() if odds > 1}
                    if len(inv) != 120:
                        continue
                    denom = sum(inv.values())
                    q = {t: v / denom for t, v in inv.items()}
                    sm, sx = sc
                    sw = W.wave_score(
                        profile,
                        str(r.get("venue_id") or "").zfill(2),
                        wind_bucket(wind),
                    )
                    if d <= cut:
                        for weight in W.WGRID:
                            p = W.adj(q, sm, sx, sw, bm, bx, weight)
                            losses[weight] += -math.log(max(p[actual], W.EPS))
                        train_n += 1
                cur = mx
            best = min(W.WGRID, key=lambda x: losses[x] / max(train_n, 1))
            selected.append(best)
            top = sorted(W.WGRID, key=lambda x: losses[x])[:4]
            print(
                f"BAO_WIND_SELECT=split:{si} weight:{best:.2f} train_n:{train_n} top:"
                + ",".join(f"{x:.2f}:{losses[x]/max(train_n,1):.6f}" for x in top),
                flush=True,
            )
            cur = date(ta.year, ta.month, 1)
            while cur <= tb:
                mx = W.nextm(cur)
                a = max(cur, ta)
                b = min(mx, tb + timedelta(days=1))
                races, eb, xb, weather, ob, rr = rows_for_month(conn, a, b)
                for r in races:
                    rid = str(r["race_id"])
                    actual = rr.get(rid, "")
                    wind = weather.get(rid)
                    om = ob.get(rid, {})
                    sc = W.entry_scores(eb.get(rid, []), xb.get(rid, []))
                    if wind is None or sc is None or len(om) != 120 or actual not in om:
                        continue
                    inv = {t: 1.0 / odds for t, odds in om.items() if odds > 1}
                    if len(inv) != 120:
                        continue
                    denom = sum(inv.values())
                    q = {t: v / denom for t, v in inv.items()}
                    sm, sx = sc
                    sw = W.wave_score(
                        profile,
                        str(r.get("venue_id") or "").zfill(2),
                        wind_bucket(wind),
                    )
                    base = W.adj(q, sm, sx, sw, bm, bx, 0.0)
                    joint = W.adj(q, sm, sx, sw, bm, bx, best)
                    W.stat_add(test, base, joint, actual)
                    W.stat_add(months[r["race_date"].strftime("%Y-%m")], base, joint, actual)
                cur = mx
            W.merge(overall, test)
            print(
                f"BAO_WIND_SPLIT={si} test:{ta}..{tb} motor:{bm:.2f} "
                f"exhibition:{bx:.2f} wind:{best:.2f} {W.fmt(test)}",
                flush=True,
            )
    print("BAO_WIND_SELECTED_WEIGHTS=" + ",".join(f"{x:.2f}" for x in selected), flush=True)
    negative = 0
    for month in sorted(months):
        stat = months[month]
        negative += int(stat["ds"] / stat["n"] < 0)
        print(f"BAO_WIND_MONTH={month} {W.fmt(stat)}", flush=True)
    print(f"BAO_WIND_MONTH_STABILITY=negative:{negative}/{len(months)}", flush=True)
    print("BAO_WIND_ALL=" + W.fmt(overall), flush=True)
    n = overall["n"]
    delta = overall["ds"] / n if n else 0.0
    var = max(0.0, (overall["d2"] - overall["ds"] ** 2 / n) / (n - 1)) if n > 1 else 0.0
    se = math.sqrt(var / n) if n else 0.0
    robust = (
        n > 0
        and delta < 0
        and all(weight > 0 for weight in selected)
        and negative >= 6
        and (se == 0 or delta / se <= -2)
    )
    print("BAO_WIND_VERDICT=" + ("ROBUST_CANDIDATE" if robust else "NOT_YET_ROBUST"), flush=True)
    print("BAO_WIND_POLICY=no_production_change", flush=True)
    print("BAO_WIND_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
