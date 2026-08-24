# -*- coding: utf-8 -*-
"""Read-only historical OOS stratification for Opponent Pressure.

Reuses the already-fixed historical opponent-pressure design:
- train-only own_class x own_lane x opponent_lane x opponent_class effects
- SHRINK_K=100
- conditional support >=40
- baseline support >=500
- the same three historical train cutoffs

No hyperparameter search, threshold tuning, DB writes, Production/LINE changes,
or promotion decisions. The only added diagnostics are fixed venue and
R01-04/R05-08/R09-12 strata, plus winner logloss/rank on complete six-lane races.
"""
from __future__ import annotations

from datetime import date
import os

import psycopg
from psycopg.rows import dict_row

DB = os.environ.get("DATABASE_URL", "").strip()
START = date(2025, 7, 1)
END = date(2026, 8, 22)
SPLITS = (date(2026, 3, 31), date(2026, 4, 30), date(2026, 5, 31))
SHRINK_K = 100.0
TRAIN_COND_MIN = 40
TRAIN_BASE_MIN = 500


def audit(conn: psycopg.Connection, split: date) -> list[dict]:
    q = """
    with base as (
      select r.race_date,r.race_id,
             coalesce(nullif(r.venue_id::text,''),nullif(r.venue_code::text,''),'') venue,
             r.race_no,
             a.lane own_lane,a.racer_class own_class,
             b.lane opp_lane,b.racer_class opp_class,
             case when re.finish_position=1 then 1.0 else 0.0 end win,
             case when re.finish_position between 1 and 3 then 1.0 else 0.0 end top3
      from v2_race_entries a
      join v2_race_entries b on b.race_id=a.race_id and b.lane<>a.lane
      join v2_races r on r.race_id=a.race_id
      join v2_result_entries re on re.race_id=a.race_id and re.lane=a.lane
      where r.race_date between %s and %s
        and a.racer_class between 1 and 4 and b.racer_class between 1 and 4
        and re.finish_position between 1 and 6
    ),
    tbase as (
      select own_class,own_lane,count(*)/5.0 n,avg(win) pwin,avg(top3) ptop3
      from base where race_date<=%s group by 1,2
    ),
    teff as (
      select b.own_class,b.own_lane,b.opp_lane,b.opp_class,count(*) n,
             (avg(b.win)-tb.pwin) * (count(*)::float8/(count(*)+%s)) ewin,
             (avg(b.top3)-tb.ptop3) * (count(*)::float8/(count(*)+%s)) etop3
      from base b join tbase tb using(own_class,own_lane)
      where b.race_date<=%s and tb.n>=%s
      group by b.own_class,b.own_lane,b.opp_lane,b.opp_class,tb.pwin,tb.ptop3
      having count(*)>=%s
    ),
    scored as (
      select b.race_id,b.race_date,b.venue,b.race_no,b.own_lane,b.own_class,
             max(b.win) win,max(b.top3) top3,tb.pwin,tb.ptop3,
             avg(coalesce(t.ewin,0)) score_win,
             avg(coalesce(t.etop3,0)) score_top3,
             count(t.opp_lane) matched_opp
      from base b
      join tbase tb using(own_class,own_lane)
      left join teff t using(own_class,own_lane,opp_lane,opp_class)
      where b.race_date>%s and tb.n>=%s
      group by b.race_id,b.race_date,b.venue,b.race_no,b.own_lane,b.own_class,tb.pwin,tb.ptop3
    ),
    pred as (
      select *,greatest(.001,least(.999,pwin+score_win)) pwin_adj,
               greatest(.001,least(.999,ptop3+score_top3)) ptop3_adj
      from scored where matched_opp>=4
    ),
    six as (
      select *,count(*) over(partition by race_id) lane_count
      from pred
    ),
    ranked as (
      select *,
        greatest(.001,pwin)/sum(greatest(.001,pwin)) over(partition by race_id) pwin_norm_base,
        greatest(.001,pwin_adj)/sum(greatest(.001,pwin_adj)) over(partition by race_id) pwin_norm_adj,
        rank() over(partition by race_id order by pwin desc) winner_rank_base,
        rank() over(partition by race_id order by pwin_adj desc) winner_rank_adj,
        case when race_no between 1 and 4 then 'R01_04'
             when race_no between 5 and 8 then 'R05_08'
             when race_no between 9 and 12 then 'R09_12'
             else 'R_OTHER' end race_band,
        lpad(venue,2,'0') venue_code
      from six where lane_count=6
    ),
    overall as (
      select 'OVERALL'::text group_type,'ALL'::text group_value,
             count(distinct race_id) n_races,count(*) n_lanes,
             avg((win-pwin)^2) win_brier_base,avg((win-pwin_adj)^2) win_brier_adj,
             avg((top3-ptop3)^2) top3_brier_base,avg((top3-ptop3_adj)^2) top3_brier_adj,
             avg(-ln(pwin_norm_base)) filter(where win=1) winner_logloss_base,
             avg(-ln(pwin_norm_adj)) filter(where win=1) winner_logloss_adj,
             avg(winner_rank_base) filter(where win=1) winner_rank_base,
             avg(winner_rank_adj) filter(where win=1) winner_rank_adj
      from ranked
    ),
    bands as (
      select 'RACE_BAND'::text group_type,race_band group_value,
             count(distinct race_id) n_races,count(*) n_lanes,
             avg((win-pwin)^2) win_brier_base,avg((win-pwin_adj)^2) win_brier_adj,
             avg((top3-ptop3)^2) top3_brier_base,avg((top3-ptop3_adj)^2) top3_brier_adj,
             avg(-ln(pwin_norm_base)) filter(where win=1) winner_logloss_base,
             avg(-ln(pwin_norm_adj)) filter(where win=1) winner_logloss_adj,
             avg(winner_rank_base) filter(where win=1) winner_rank_base,
             avg(winner_rank_adj) filter(where win=1) winner_rank_adj
      from ranked group by race_band
    ),
    venues as (
      select 'VENUE'::text group_type,venue_code group_value,
             count(distinct race_id) n_races,count(*) n_lanes,
             avg((win-pwin)^2) win_brier_base,avg((win-pwin_adj)^2) win_brier_adj,
             avg((top3-ptop3)^2) top3_brier_base,avg((top3-ptop3_adj)^2) top3_brier_adj,
             avg(-ln(pwin_norm_base)) filter(where win=1) winner_logloss_base,
             avg(-ln(pwin_norm_adj)) filter(where win=1) winner_logloss_adj,
             avg(winner_rank_base) filter(where win=1) winner_rank_base,
             avg(winner_rank_adj) filter(where win=1) winner_rank_adj
      from ranked group by venue_code
    )
    select * from overall
    union all select * from bands
    union all select * from venues
    order by group_type,group_value
    """
    params = (
        START, END, split, SHRINK_K, SHRINK_K, split,
        TRAIN_BASE_MIN, TRAIN_COND_MIN, split, TRAIN_BASE_MIN,
    )
    with conn.cursor() as cur:
        cur.execute(q, params)
        return [dict(r) for r in cur.fetchall()]


def emit(split: date, row: dict) -> None:
    n = int(row.get("n_races") or 0)
    wb = float(row.get("win_brier_base") or 0)
    wa = float(row.get("win_brier_adj") or 0)
    tb = float(row.get("top3_brier_base") or 0)
    ta = float(row.get("top3_brier_adj") or 0)
    lb = float(row.get("winner_logloss_base") or 0)
    la = float(row.get("winner_logloss_adj") or 0)
    rb = float(row.get("winner_rank_base") or 0)
    ra = float(row.get("winner_rank_adj") or 0)
    print(
        f"OPP_PRESSURE_OOS_STRAT={split}|{row['group_type']}:{row['group_value']} n:{n} "
        f"win_brier_base:{wb:.8f} win_brier_adj:{wa:.8f} win_delta:{wa-wb:+.8f} "
        f"top3_brier_base:{tb:.8f} top3_brier_adj:{ta:.8f} top3_delta:{ta-tb:+.8f} "
        f"winner_logloss_base:{lb:.8f} winner_logloss_adj:{la:.8f} logloss_delta:{la-lb:+.8f} "
        f"winner_rank_base:{rb:.4f} winner_rank_adj:{ra:.4f} rank_delta:{ra-rb:+.4f}",
        flush=True,
    )


def main() -> None:
    if not DB:
        raise RuntimeError("DATABASE_URL required")
    print("OPP_PRESSURE_OOS_STRAT_MODE=read_only_fixed_historical_design_no_tuning", flush=True)
    print(f"OPP_PRESSURE_OOS_STRAT_PERIOD={START}..{END}", flush=True)
    print(
        f"OPP_PRESSURE_OOS_STRAT_GATES=train_cond>={TRAIN_COND_MIN},train_base>={TRAIN_BASE_MIN},shrink_k={SHRINK_K}",
        flush=True,
    )
    print("OPP_PRESSURE_OOS_STRAT_SPLITS=2026-03-31,2026-04-30,2026-05-31", flush=True)
    print("OPP_PRESSURE_OOS_STRAT_STRATA=venue_and_fixed_race_bands_R01_04_R05_08_R09_12", flush=True)
    print("OPP_PRESSURE_OOS_STRAT_POLICY=complete6_only_train_only_effects_no_writes_no_production_no_line", flush=True)
    with psycopg.connect(DB, row_factory=dict_row, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("set max_parallel_workers_per_gather=0")
            cur.execute("set work_mem='8MB'")
            cur.execute("set statement_timeout='240s'")
        for split in SPLITS:
            rows = audit(conn, split)
            for row in rows:
                emit(split, row)
    print("OPP_PRESSURE_OOS_STRAT_INTERPRETATION=historical_stability_crosscheck_only_no_subgroup_selection", flush=True)
    print("OPP_PRESSURE_OOS_STRAT_PROMOTION=BLOCK_NO_PRODUCTION_CHANGE", flush=True)
    print("OPP_PRESSURE_OOS_STRAT_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        msg = str(exc).replace("\n", " ").replace("\r", " ")[:700]
        print(f"OPP_PRESSURE_OOS_STRAT_ERROR={type(exc).__name__}:{msg}", flush=True)
        raise
