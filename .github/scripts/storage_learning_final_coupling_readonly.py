# -*- coding: utf-8 -*-
"""Read-only audit for cross-label realtime-odds movement coupling.

Capacity/redundancy research only. The current collector computes prev_odds from
the latest row for a race without filtering snapshot_label. This audit measures
how often a current final_ab row demonstrably used the current learning_all row
as its immediate previous odds sample, estimates a one-step counterfactual
movement flag using learning_all.prev_odds, and measures overlap with saved final
judgement rows without writing anything.

The counterfactual is deliberately labelled a proxy: realtime tables retain one
current row per (race_id, snapshot_label, ticket), so older same-label snapshots
are not retained as an independent history table.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


def one(sql: str):
    rows = fetch_all(sql)
    return dict(rows[0]) if rows else {}


def main() -> None:
    print("STORAGE_LEARNING_FINAL_COUPLING_MODE=READ_ONLY_NO_MUTATION")

    evidence = one(
        """
        with f as (
          select race_id,ticket,race_date,snapshot_at,odds,prev_odds,
                 market_rank,prev_market_rank,is_odds_drift,is_odds_steam
            from v2_realtime_odds_snapshots
           where snapshot_label='final_ab'
        ), l as (
          select race_id,ticket,race_date,snapshot_at,odds,prev_odds,
                 market_rank,prev_market_rank,is_odds_drift,is_odds_steam
            from v2_realtime_odds_snapshots
           where snapshot_label='learning_all'
        ), j as (
          select f.*, l.snapshot_at as learning_at,
                 l.odds as learning_odds,
                 l.prev_odds as learning_prev_odds,
                 l.market_rank as learning_market_rank,
                 extract(epoch from (f.snapshot_at-l.snapshot_at)) as learning_to_final_seconds
            from f join l using (race_id,ticket)
        )
        select
          count(*)::bigint as overlap_rows,
          count(*) filter (where learning_at < snapshot_at)::bigint as learning_before_final,
          count(*) filter (where learning_at > snapshot_at)::bigint as final_before_learning,
          count(*) filter (
            where learning_at < snapshot_at
              and prev_odds is not distinct from learning_odds
          )::bigint as direct_prev_odds_matches,
          count(*) filter (
            where learning_at < snapshot_at
              and prev_odds is not distinct from learning_odds
              and prev_market_rank is not distinct from learning_market_rank
          )::bigint as direct_prev_odds_rank_matches,
          count(*) filter (
            where learning_at < snapshot_at
              and prev_odds is not distinct from learning_odds
              and learning_prev_odds is not null
              and learning_prev_odds > 0
          )::bigint as direct_with_counterfactual_proxy,
          count(*) filter (
            where learning_at < snapshot_at
              and prev_odds is not distinct from learning_odds
              and learning_to_final_seconds between 0 and 180
          )::bigint as direct_within_180s,
          count(*) filter (
            where learning_at < snapshot_at
              and prev_odds is not distinct from learning_odds
              and race_date >= current_date - 7
              and race_date < current_date
          )::bigint as recent7_direct_prev_matches,
          min(learning_to_final_seconds) filter (
            where learning_at < snapshot_at
              and prev_odds is not distinct from learning_odds
          ) as min_direct_gap_seconds,
          max(learning_to_final_seconds) filter (
            where learning_at < snapshot_at
              and prev_odds is not distinct from learning_odds
          ) as max_direct_gap_seconds,
          avg(learning_to_final_seconds) filter (
            where learning_at < snapshot_at
              and prev_odds is not distinct from learning_odds
          ) as avg_direct_gap_seconds
        from j
        """
    )

    proxy = one(
        """
        with f as (
          select race_id,ticket,race_date,snapshot_at,odds,prev_odds,
                 is_odds_drift,is_odds_steam
            from v2_realtime_odds_snapshots
           where snapshot_label='final_ab'
        ), l as (
          select race_id,ticket,snapshot_at,odds,prev_odds
            from v2_realtime_odds_snapshots
           where snapshot_label='learning_all'
        ), base as (
          select f.*,
                 l.snapshot_at as learning_at,
                 l.odds as learning_odds,
                 l.prev_odds as learning_prev_odds,
                 round(((f.odds-l.prev_odds)/l.prev_odds)::numeric,4) as proxy_delta_pct
            from f join l using (race_id,ticket)
           where l.snapshot_at < f.snapshot_at
             and f.prev_odds is not distinct from l.odds
             and l.prev_odds is not null
             and l.prev_odds > 0
             and f.odds is not null
        ), scored as (
          select *,
                 (proxy_delta_pct >= 0.15) as proxy_drift,
                 (proxy_delta_pct <= -0.15) as proxy_steam,
                 (case when is_odds_steam then 0.3 else 0 end
                  + case when is_odds_drift then -0.5 else 0 end)::numeric as stored_move_score,
                 (case when proxy_delta_pct <= -0.15 then 0.3 else 0 end
                  + case when proxy_delta_pct >= 0.15 then -0.5 else 0 end)::numeric as proxy_move_score
            from base
        )
        select
          count(*)::bigint as proxy_rows,
          count(*) filter (where is_odds_drift)::bigint as stored_drift_rows,
          count(*) filter (where proxy_drift)::bigint as proxy_drift_rows,
          count(*) filter (where is_odds_steam)::bigint as stored_steam_rows,
          count(*) filter (where proxy_steam)::bigint as proxy_steam_rows,
          count(*) filter (
            where is_odds_drift is distinct from proxy_drift
               or is_odds_steam is distinct from proxy_steam
          )::bigint as movement_flag_changed_rows,
          count(*) filter (
            where stored_move_score is distinct from proxy_move_score
          )::bigint as movement_score_changed_rows,
          count(*) filter (
            where proxy_move_score > stored_move_score
          )::bigint as proxy_score_higher_rows,
          count(*) filter (
            where proxy_move_score < stored_move_score
          )::bigint as proxy_score_lower_rows,
          count(*) filter (
            where race_date >= current_date - 7
              and race_date < current_date
              and stored_move_score is distinct from proxy_move_score
          )::bigint as recent7_score_changed_rows,
          min(proxy_move_score-stored_move_score) as min_score_delta,
          max(proxy_move_score-stored_move_score) as max_score_delta
        from scored
        """
    )

    decisions = one(
        """
        with d as (
          select race_id,ticket,race_date,recommendation,skip_reason,realtime_score
            from v2_realtime_decisions
           where decision_label='final_ab'
        ), f as (
          select race_id,ticket,snapshot_at,odds,prev_odds,
                 is_odds_drift,is_odds_steam
            from v2_realtime_odds_snapshots
           where snapshot_label='final_ab'
        ), l as (
          select race_id,ticket,snapshot_at,odds,prev_odds
            from v2_realtime_odds_snapshots
           where snapshot_label='learning_all'
        ), base as (
          select d.*, f.snapshot_at as final_at,
                 f.odds as final_odds, f.prev_odds as final_prev_odds,
                 f.is_odds_drift, f.is_odds_steam,
                 l.snapshot_at as learning_at,
                 l.odds as learning_odds,
                 l.prev_odds as learning_prev_odds,
                 case when l.prev_odds is not null and l.prev_odds > 0
                      then round(((f.odds-l.prev_odds)/l.prev_odds)::numeric,4)
                      else null end as proxy_delta_pct
            from d
            left join f using (race_id,ticket)
            left join l using (race_id,ticket)
        ), direct as (
          select *,
                 (case when is_odds_steam then 0.3 else 0 end
                  + case when is_odds_drift then -0.5 else 0 end)::numeric as stored_move_score,
                 (case when proxy_delta_pct <= -0.15 then 0.3 else 0 end
                  + case when proxy_delta_pct >= 0.15 then -0.5 else 0 end)::numeric as proxy_move_score
            from base
           where learning_at < final_at
             and final_prev_odds is not distinct from learning_odds
        ), calc as (
          select *,
                 case when proxy_delta_pct is not null and realtime_score is not null
                      then realtime_score - stored_move_score + proxy_move_score
                      else null end as proxy_realtime_score
            from direct
        ), recalc as (
          select *,
                 case
                   when proxy_realtime_score is null then null
                   when skip_reason is not null and btrim(skip_reason) <> '' then 'skip'
                   when proxy_realtime_score >= 1.0 then 'buy'
                   when proxy_realtime_score >= 0.0 then 'watch'
                   else 'skip'
                 end as proxy_recommendation
            from calc
        )
        select
          (select count(*) from d)::bigint as final_decision_rows,
          (select count(distinct race_id) from d)::bigint as final_decision_races,
          count(*)::bigint as direct_coupled_decision_rows,
          count(distinct race_id)::bigint as direct_coupled_decision_races,
          count(*) filter (where lower(coalesce(recommendation,''))='buy')::bigint as direct_buy_rows,
          count(*) filter (where lower(coalesce(recommendation,''))='watch')::bigint as direct_watch_rows,
          count(*) filter (where lower(coalesce(recommendation,''))='skip')::bigint as direct_skip_rows,
          count(*) filter (where is_odds_drift)::bigint as direct_stored_drift_rows,
          count(*) filter (where is_odds_steam)::bigint as direct_stored_steam_rows,
          count(*) filter (where proxy_realtime_score is not null)::bigint as decision_proxy_rows,
          count(*) filter (
            where proxy_recommendation is not null
              and lower(coalesce(recommendation,'')) is distinct from proxy_recommendation
          )::bigint as proxy_recommendation_changed_rows,
          count(*) filter (
            where lower(coalesce(recommendation,''))='buy'
              and proxy_recommendation is distinct from 'buy'
          )::bigint as proxy_buy_to_other_rows,
          count(*) filter (
            where lower(coalesce(recommendation,''))<>'buy'
              and proxy_recommendation='buy'
          )::bigint as proxy_other_to_buy_rows,
          count(*) filter (
            where race_date >= current_date - 7
              and race_date < current_date
              and proxy_recommendation is not null
              and lower(coalesce(recommendation,'')) is distinct from proxy_recommendation
          )::bigint as recent7_proxy_recommendation_changed_rows
        from recalc
        """
    )

    print(
        "STORAGE_LEARNING_FINAL_COUPLING_EVIDENCE="
        f"overlap_rows:{int(evidence.get('overlap_rows') or 0)} "
        f"learning_before_final:{int(evidence.get('learning_before_final') or 0)} "
        f"final_before_learning:{int(evidence.get('final_before_learning') or 0)} "
        f"direct_prev_odds_matches:{int(evidence.get('direct_prev_odds_matches') or 0)} "
        f"direct_prev_odds_rank_matches:{int(evidence.get('direct_prev_odds_rank_matches') or 0)} "
        f"direct_with_counterfactual_proxy:{int(evidence.get('direct_with_counterfactual_proxy') or 0)} "
        f"direct_within_180s:{int(evidence.get('direct_within_180s') or 0)} "
        f"recent7_direct_prev_matches:{int(evidence.get('recent7_direct_prev_matches') or 0)} "
        f"min_direct_gap_seconds:{evidence.get('min_direct_gap_seconds')} "
        f"max_direct_gap_seconds:{evidence.get('max_direct_gap_seconds')} "
        f"avg_direct_gap_seconds:{evidence.get('avg_direct_gap_seconds')}"
    )
    print(
        "STORAGE_LEARNING_FINAL_COUNTERFACTUAL_PROXY="
        f"proxy_rows:{int(proxy.get('proxy_rows') or 0)} "
        f"stored_drift_rows:{int(proxy.get('stored_drift_rows') or 0)} "
        f"proxy_drift_rows:{int(proxy.get('proxy_drift_rows') or 0)} "
        f"stored_steam_rows:{int(proxy.get('stored_steam_rows') or 0)} "
        f"proxy_steam_rows:{int(proxy.get('proxy_steam_rows') or 0)} "
        f"movement_flag_changed_rows:{int(proxy.get('movement_flag_changed_rows') or 0)} "
        f"movement_score_changed_rows:{int(proxy.get('movement_score_changed_rows') or 0)} "
        f"proxy_score_higher_rows:{int(proxy.get('proxy_score_higher_rows') or 0)} "
        f"proxy_score_lower_rows:{int(proxy.get('proxy_score_lower_rows') or 0)} "
        f"recent7_score_changed_rows:{int(proxy.get('recent7_score_changed_rows') or 0)} "
        f"min_score_delta:{proxy.get('min_score_delta')} "
        f"max_score_delta:{proxy.get('max_score_delta')}"
    )
    print(
        "STORAGE_LEARNING_FINAL_DECISION_PROXY="
        f"final_decision_rows:{int(decisions.get('final_decision_rows') or 0)} "
        f"final_decision_races:{int(decisions.get('final_decision_races') or 0)} "
        f"direct_coupled_decision_rows:{int(decisions.get('direct_coupled_decision_rows') or 0)} "
        f"direct_coupled_decision_races:{int(decisions.get('direct_coupled_decision_races') or 0)} "
        f"direct_buy_rows:{int(decisions.get('direct_buy_rows') or 0)} "
        f"direct_watch_rows:{int(decisions.get('direct_watch_rows') or 0)} "
        f"direct_skip_rows:{int(decisions.get('direct_skip_rows') or 0)} "
        f"direct_stored_drift_rows:{int(decisions.get('direct_stored_drift_rows') or 0)} "
        f"direct_stored_steam_rows:{int(decisions.get('direct_stored_steam_rows') or 0)} "
        f"decision_proxy_rows:{int(decisions.get('decision_proxy_rows') or 0)} "
        f"proxy_recommendation_changed_rows:{int(decisions.get('proxy_recommendation_changed_rows') or 0)} "
        f"proxy_buy_to_other_rows:{int(decisions.get('proxy_buy_to_other_rows') or 0)} "
        f"proxy_other_to_buy_rows:{int(decisions.get('proxy_other_to_buy_rows') or 0)} "
        f"recent7_proxy_recommendation_changed_rows:{int(decisions.get('recent7_proxy_recommendation_changed_rows') or 0)}"
    )
    print("STORAGE_LEARNING_FINAL_COUPLING_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
