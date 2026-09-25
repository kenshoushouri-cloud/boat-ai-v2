# -*- coding: utf-8 -*-
"""Read-only inventory for the large historical trifecta-odds relation.

Capacity research only. This script performs SELECT/catalog queries and never
mutates Production data, schema, Railway settings, LINE state, or purchases.
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
    catalog = one(
        """
        select
          pg_total_relation_size(c.oid) as total_bytes,
          pg_relation_size(c.oid) as heap_bytes,
          pg_indexes_size(c.oid) as index_bytes,
          c.reltuples::bigint as planner_rows,
          c.relpages::bigint as relpages,
          coalesce(s.n_live_tup,0)::bigint as stats_live_rows,
          coalesce(s.n_dead_tup,0)::bigint as stats_dead_rows,
          s.last_vacuum,
          s.last_autovacuum,
          s.last_analyze,
          s.last_autoanalyze,
          coalesce(s.vacuum_count,0)::bigint as vacuum_count,
          coalesce(s.autovacuum_count,0)::bigint as autovacuum_count,
          coalesce(s.analyze_count,0)::bigint as analyze_count,
          coalesce(s.autoanalyze_count,0)::bigint as autoanalyze_count
        from pg_class c
        left join pg_stat_user_tables s on s.relid=c.oid
        where c.oid='public.v2_odds_trifecta'::regclass
        """
    )

    exact = one(
        """
        select
          count(*)::bigint as exact_rows,
          count(*) filter (where is_final is false)::bigint as nonfinal_rows,
          count(*) filter (where is_final is null)::bigint as null_final_rows,
          count(*) filter (where fetched_at is null)::bigint as null_fetched_rows,
          min(fetched_at) as min_fetched_at,
          max(fetched_at) as max_fetched_at
        from v2_odds_trifecta
        """
    )

    race_span = one(
        """
        select
          min(o.race_id) as min_race_id,
          max(o.race_id) as max_race_id,
          min(r.race_date) as min_race_date,
          max(r.race_date) as max_race_date,
          count(*) filter (where r.race_id is null)::bigint as orphan_rows
        from v2_odds_trifecta o
        left join v2_races r on r.race_id=o.race_id
        """
    )

    identities = one(
        """
        select
          count(*)::bigint as race_count,
          min(ticket_rows)::bigint as min_ticket_rows,
          max(ticket_rows)::bigint as max_ticket_rows,
          count(*) filter (where ticket_rows=120)::bigint as races_120,
          count(*) filter (where ticket_rows=60)::bigint as races_60,
          count(*) filter (where ticket_rows=24)::bigint as races_24,
          count(*) filter (where ticket_rows not in (120,60,24))::bigint as races_other
        from (
          select race_id,count(*)::bigint as ticket_rows
          from v2_odds_trifecta
          group by race_id
        ) x
        """
    )

    indexes = fetch_all(
        """
        select
          i.relname as index_name,
          pg_relation_size(i.oid) as index_bytes,
          ix.indisunique,
          ix.indisprimary
        from pg_index ix
        join pg_class t on t.oid=ix.indrelid
        join pg_class i on i.oid=ix.indexrelid
        where t.oid='public.v2_odds_trifecta'::regclass
        order by pg_relation_size(i.oid) desc,i.relname
        """
    )

    print('STORAGE_ODDS_TRIFECTA_MODE=READ_ONLY_NO_MUTATION')
    print(
        'STORAGE_ODDS_TRIFECTA_RELATION='
        f"total_bytes:{int(catalog.get('total_bytes') or 0)} "
        f"heap_bytes:{int(catalog.get('heap_bytes') or 0)} "
        f"index_bytes:{int(catalog.get('index_bytes') or 0)} "
        f"planner_rows:{int(catalog.get('planner_rows') or 0)} "
        f"relpages:{int(catalog.get('relpages') or 0)}"
    )
    print(
        'STORAGE_ODDS_TRIFECTA_STATS='
        f"live:{int(catalog.get('stats_live_rows') or 0)} dead:{int(catalog.get('stats_dead_rows') or 0)} "
        f"last_vacuum:{catalog.get('last_vacuum')} last_autovacuum:{catalog.get('last_autovacuum')} "
        f"last_analyze:{catalog.get('last_analyze')} last_autoanalyze:{catalog.get('last_autoanalyze')} "
        f"vacuum_count:{int(catalog.get('vacuum_count') or 0)} autovacuum_count:{int(catalog.get('autovacuum_count') or 0)} "
        f"analyze_count:{int(catalog.get('analyze_count') or 0)} autoanalyze_count:{int(catalog.get('autoanalyze_count') or 0)}"
    )
    print(
        'STORAGE_ODDS_TRIFECTA_EXACT='
        f"rows:{int(exact.get('exact_rows') or 0)} nonfinal:{int(exact.get('nonfinal_rows') or 0)} "
        f"null_final:{int(exact.get('null_final_rows') or 0)} null_fetched:{int(exact.get('null_fetched_rows') or 0)} "
        f"min_fetched:{exact.get('min_fetched_at')} max_fetched:{exact.get('max_fetched_at')}"
    )
    print(
        'STORAGE_ODDS_TRIFECTA_SPAN='
        f"min_race_id:{race_span.get('min_race_id')} max_race_id:{race_span.get('max_race_id')} "
        f"min_date:{race_span.get('min_race_date')} max_date:{race_span.get('max_race_date')} "
        f"orphan_rows:{int(race_span.get('orphan_rows') or 0)}"
    )
    print(
        'STORAGE_ODDS_TRIFECTA_RACES='
        f"races:{int(identities.get('race_count') or 0)} "
        f"min_ticket_rows:{int(identities.get('min_ticket_rows') or 0)} "
        f"max_ticket_rows:{int(identities.get('max_ticket_rows') or 0)} "
        f"races_120:{int(identities.get('races_120') or 0)} "
        f"races_60:{int(identities.get('races_60') or 0)} "
        f"races_24:{int(identities.get('races_24') or 0)} "
        f"races_other:{int(identities.get('races_other') or 0)}"
    )
    for row in indexes:
        print(
            'STORAGE_ODDS_TRIFECTA_INDEX='
            f"name:{row.get('index_name')} bytes:{int(row.get('index_bytes') or 0)} "
            f"unique:{str(bool(row.get('indisunique'))).lower()} "
            f"primary:{str(bool(row.get('indisprimary'))).lower()}"
        )

    # The compatibility contract requires a unique (race_id,ticket) identity.
    # We verify the index metadata rather than issuing another full-table distinct scan.
    unique_identity = any(
        str(row.get('index_name') or '') == 'ux_v2_odds_trifecta_race_ticket'
        and bool(row.get('indisunique'))
        for row in indexes
    )
    print(f'STORAGE_ODDS_TRIFECTA_UNIQUE_IDENTITY={str(unique_identity).lower()}')
    if not unique_identity:
        raise SystemExit('STORAGE_ODDS_TRIFECTA_RESULT=BLOCK_IDENTITY_INDEX_MISSING')
    print('STORAGE_ODDS_TRIFECTA_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
