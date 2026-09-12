# -*- coding: utf-8 -*-
"""Read-only label/overlap inventory for realtime trifecta odds snapshots.

Capacity research only. SELECT/catalog queries only; no cleanup, schema change,
Railway change, LINE action, model change, or purchase action.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


def one(sql: str, params=()):
    rows = fetch_all(sql, params)
    return dict(rows[0]) if rows else {}


def main() -> None:
    relation = one(
        """
        select
          pg_total_relation_size('public.v2_realtime_odds_snapshots') as total_bytes,
          pg_relation_size('public.v2_realtime_odds_snapshots') as heap_bytes,
          pg_indexes_size('public.v2_realtime_odds_snapshots') as index_bytes
        """
    )
    exact = one(
        """
        select count(*)::bigint as rows,
               count(distinct race_id)::bigint as races,
               count(distinct snapshot_label)::bigint as labels,
               min(race_date) as min_date,max(race_date) as max_date,
               min(snapshot_at) as min_at,max(snapshot_at) as max_at
          from v2_realtime_odds_snapshots
        """
    )
    labels = fetch_all(
        """
        select snapshot_label,
               count(*)::bigint as rows,
               count(distinct race_id)::bigint as races,
               min(race_date) as min_date,max(race_date) as max_date,
               min(snapshot_at) as min_at,max(snapshot_at) as max_at
          from v2_realtime_odds_snapshots
         group by snapshot_label
         order by count(*) desc,snapshot_label
        """
    )
    pair = one(
        """
        with f as (
          select race_id,ticket,odds,snapshot_at,
                 market_rank,prev_odds,odds_delta,odds_delta_pct,
                 prev_market_rank,market_rank_delta,is_favorite,
                 is_odds_too_low,is_odds_drift,is_odds_steam
            from v2_realtime_odds_snapshots
           where snapshot_label='final_ab'
        ), l as (
          select race_id,ticket,odds,snapshot_at,
                 market_rank,prev_odds,odds_delta,odds_delta_pct,
                 prev_market_rank,market_rank_delta,is_favorite,
                 is_odds_too_low,is_odds_drift,is_odds_steam
            from v2_realtime_odds_snapshots
           where snapshot_label='learning_all'
        )
        select
          count(*)::bigint as overlap_rows,
          count(distinct f.race_id)::bigint as overlap_races,
          count(*) filter (where f.odds is not distinct from l.odds)::bigint as equal_odds,
          count(*) filter (where f.odds is distinct from l.odds)::bigint as different_odds,
          count(*) filter (where f.market_rank is not distinct from l.market_rank)::bigint as equal_market_rank,
          count(*) filter (where f.prev_odds is not distinct from l.prev_odds)::bigint as equal_prev_odds,
          count(*) filter (where f.odds_delta is not distinct from l.odds_delta)::bigint as equal_odds_delta,
          count(*) filter (where f.odds_delta_pct is not distinct from l.odds_delta_pct)::bigint as equal_odds_delta_pct,
          count(*) filter (
            where f.market_rank is not distinct from l.market_rank
              and f.prev_odds is not distinct from l.prev_odds
              and f.odds_delta is not distinct from l.odds_delta
              and f.odds_delta_pct is not distinct from l.odds_delta_pct
              and f.prev_market_rank is not distinct from l.prev_market_rank
              and f.market_rank_delta is not distinct from l.market_rank_delta
              and f.is_favorite is not distinct from l.is_favorite
              and f.is_odds_too_low is not distinct from l.is_odds_too_low
              and f.is_odds_drift is not distinct from l.is_odds_drift
              and f.is_odds_steam is not distinct from l.is_odds_steam
          )::bigint as equal_movement_features,
          count(*) filter (where f.snapshot_at > l.snapshot_at)::bigint as final_after_learning,
          count(*) filter (where l.snapshot_at > f.snapshot_at)::bigint as learning_after_final,
          count(*) filter (
            where f.snapshot_at > l.snapshot_at
              and f.prev_odds is not distinct from l.odds
              and f.prev_market_rank is not distinct from l.market_rank
          )::bigint as final_prev_matches_learning,
          count(distinct f.race_id) filter (
            where f.snapshot_at > l.snapshot_at
              and f.prev_odds is not distinct from l.odds
              and f.prev_market_rank is not distinct from l.market_rank
          )::bigint as final_prev_matches_learning_races,
          count(*) filter (
            where l.snapshot_at > f.snapshot_at
              and l.prev_odds is not distinct from f.odds
              and l.prev_market_rank is not distinct from f.market_rank
          )::bigint as learning_prev_matches_final,
          count(*) filter (
            where f.snapshot_at > l.snapshot_at
              and f.prev_odds is not distinct from l.odds
              and f.prev_market_rank is not distinct from l.market_rank
              and (coalesce(f.is_odds_drift,false) or coalesce(f.is_odds_steam,false))
          )::bigint as final_crosslabel_prev_flagged,
          count(*) filter (
            where f.snapshot_at > l.snapshot_at
              and f.prev_odds is not distinct from l.odds
              and f.prev_market_rank is not distinct from l.market_rank
              and f.market_rank=1
              and (coalesce(f.is_odds_drift,false) or coalesce(f.is_odds_steam,false))
          )::bigint as final_crosslabel_prev_rank1_flagged,
          count(distinct f.race_id) filter (
            where f.snapshot_at > l.snapshot_at
              and f.prev_odds is not distinct from l.odds
              and f.prev_market_rank is not distinct from l.market_rank
              and f.market_rank=1
              and (coalesce(f.is_odds_drift,false) or coalesce(f.is_odds_steam,false))
          )::bigint as final_crosslabel_prev_rank1_flagged_races,
          count(*) filter (where f.snapshot_at is not distinct from l.snapshot_at)::bigint as equal_snapshot_at,
          min(abs(extract(epoch from (f.snapshot_at-l.snapshot_at)))) as min_abs_seconds,
          max(abs(extract(epoch from (f.snapshot_at-l.snapshot_at)))) as max_abs_seconds,
          avg(abs(extract(epoch from (f.snapshot_at-l.snapshot_at)))) as avg_abs_seconds
        from f join l using (race_id,ticket)
        """
    )
    indexes = fetch_all(
        """
        select i.relname as index_name,
               pg_relation_size(i.oid) as index_bytes,
               ix.indisunique,ix.indisprimary
          from pg_index ix
          join pg_class t on t.oid=ix.indrelid
          join pg_class i on i.oid=ix.indexrelid
         where t.oid='public.v2_realtime_odds_snapshots'::regclass
         order by pg_relation_size(i.oid) desc,i.relname
        """
    )

    by_name = {str(r.get('snapshot_label') or ''): dict(r) for r in labels}
    final_rows = int((by_name.get('final_ab') or {}).get('rows') or 0)
    learning_rows = int((by_name.get('learning_all') or {}).get('rows') or 0)
    overlap_rows = int(pair.get('overlap_rows') or 0)
    equal_movement_features = int(pair.get('equal_movement_features') or 0)

    print('STORAGE_REALTIME_ODDS_LABEL_MODE=READ_ONLY_NO_MUTATION')
    print(
        'STORAGE_REALTIME_ODDS_RELATION='
        f"total_bytes:{int(relation.get('total_bytes') or 0)} "
        f"heap_bytes:{int(relation.get('heap_bytes') or 0)} "
        f"index_bytes:{int(relation.get('index_bytes') or 0)}"
    )
    print(
        'STORAGE_REALTIME_ODDS_EXACT='
        f"rows:{int(exact.get('rows') or 0)} races:{int(exact.get('races') or 0)} "
        f"labels:{int(exact.get('labels') or 0)} min_date:{exact.get('min_date')} "
        f"max_date:{exact.get('max_date')} min_at:{exact.get('min_at')} max_at:{exact.get('max_at')}"
    )
    for row in labels:
        print(
            'STORAGE_REALTIME_ODDS_LABEL='
            f"label:{row.get('snapshot_label')} rows:{int(row.get('rows') or 0)} "
            f"races:{int(row.get('races') or 0)} min_date:{row.get('min_date')} "
            f"max_date:{row.get('max_date')} min_at:{row.get('min_at')} max_at:{row.get('max_at')}"
        )
    print(
        'STORAGE_REALTIME_ODDS_FINAL_LEARNING_OVERLAP='
        f"final_rows:{final_rows} learning_rows:{learning_rows} overlap_rows:{overlap_rows} "
        f"final_only_rows:{max(0, final_rows-overlap_rows)} "
        f"learning_only_rows:{max(0, learning_rows-overlap_rows)} "
        f"overlap_races:{int(pair.get('overlap_races') or 0)} "
        f"equal_odds:{int(pair.get('equal_odds') or 0)} "
        f"different_odds:{int(pair.get('different_odds') or 0)} "
        f"equal_market_rank:{int(pair.get('equal_market_rank') or 0)} "
        f"equal_prev_odds:{int(pair.get('equal_prev_odds') or 0)} "
        f"equal_odds_delta:{int(pair.get('equal_odds_delta') or 0)} "
        f"equal_odds_delta_pct:{int(pair.get('equal_odds_delta_pct') or 0)} "
        f"equal_movement_features:{equal_movement_features} "
        f"different_movement_features:{max(0, overlap_rows-equal_movement_features)} "
        f"equal_snapshot_at:{int(pair.get('equal_snapshot_at') or 0)} "
        f"min_abs_seconds:{pair.get('min_abs_seconds')} "
        f"max_abs_seconds:{pair.get('max_abs_seconds')} "
        f"avg_abs_seconds:{pair.get('avg_abs_seconds')}"
    )
    print(
        'STORAGE_REALTIME_ODDS_CROSS_LABEL_PREV='
        f"final_after_learning:{int(pair.get('final_after_learning') or 0)} "
        f"learning_after_final:{int(pair.get('learning_after_final') or 0)} "
        f"final_prev_matches_learning:{int(pair.get('final_prev_matches_learning') or 0)} "
        f"final_prev_matches_learning_races:{int(pair.get('final_prev_matches_learning_races') or 0)} "
        f"learning_prev_matches_final:{int(pair.get('learning_prev_matches_final') or 0)} "
        f"final_crosslabel_prev_flagged:{int(pair.get('final_crosslabel_prev_flagged') or 0)} "
        f"final_crosslabel_prev_rank1_flagged:{int(pair.get('final_crosslabel_prev_rank1_flagged') or 0)} "
        f"final_crosslabel_prev_rank1_flagged_races:{int(pair.get('final_crosslabel_prev_rank1_flagged_races') or 0)}"
    )
    for row in indexes:
        print(
            'STORAGE_REALTIME_ODDS_INDEX='
            f"name:{row.get('index_name')} bytes:{int(row.get('index_bytes') or 0)} "
            f"unique:{str(bool(row.get('indisunique'))).lower()} "
            f"primary:{str(bool(row.get('indisprimary'))).lower()}"
        )
    print('STORAGE_REALTIME_ODDS_LABEL_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
