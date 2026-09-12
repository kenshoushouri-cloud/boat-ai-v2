# -*- coding: utf-8 -*-
"""Read-only label matrix for non-odds realtime snapshot tables.

Measures final_ab/learning_all identity overlap and payload equality while
excluding volatile identity/timestamp columns. SELECT-only capacity research.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all


TABLES = (
    ('v2_realtime_weather_snapshots', False),
    ('v2_realtime_exhibition_snapshots', True),
    ('v2_realtime_entry_snapshots', True),
    ('v2_realtime_race_condition_snapshots', False),
    ('v2_realtime_racer_condition_snapshots', True),
)


def one(sql: str):
    rows = fetch_all(sql)
    return dict(rows[0]) if rows else {}


def main() -> None:
    print('STORAGE_REALTIME_LABEL_MATRIX_MODE=READ_ONLY_NO_MUTATION')
    for table, has_lane in TABLES:
        relation = one(
            f"""
            select pg_total_relation_size('public.{table}') as total_bytes,
                   pg_relation_size('public.{table}') as heap_bytes,
                   pg_indexes_size('public.{table}') as index_bytes
            """
        )
        labels = fetch_all(
            f"""
            select snapshot_label,count(*)::bigint as rows,
                   count(distinct race_id)::bigint as races,
                   min(race_date) as min_date,max(race_date) as max_date
              from {table}
             group by snapshot_label
             order by count(*) desc,snapshot_label
            """
        )
        identity = 'f.race_id=l.race_id and f.lane=l.lane' if has_lane else 'f.race_id=l.race_id'
        pair = one(
            f"""
            with f as (select * from {table} where snapshot_label='final_ab'),
                 l as (select * from {table} where snapshot_label='learning_all')
            select count(*)::bigint as overlap_rows,
                   count(distinct f.race_id)::bigint as overlap_races,
                   count(*) filter (
                     where (to_jsonb(f)-'id'-'snapshot_label'-'snapshot_at'-'created_at'-'updated_at')
                         = (to_jsonb(l)-'id'-'snapshot_label'-'snapshot_at'-'created_at'-'updated_at')
                   )::bigint as equal_payload_rows,
                   count(*) filter (
                     where (to_jsonb(f)-'id'-'snapshot_label'-'snapshot_at'-'created_at'-'updated_at')
                        <> (to_jsonb(l)-'id'-'snapshot_label'-'snapshot_at'-'created_at'-'updated_at')
                   )::bigint as different_payload_rows,
                   min(abs(extract(epoch from (f.snapshot_at-l.snapshot_at)))) as min_abs_seconds,
                   max(abs(extract(epoch from (f.snapshot_at-l.snapshot_at)))) as max_abs_seconds,
                   avg(abs(extract(epoch from (f.snapshot_at-l.snapshot_at)))) as avg_abs_seconds
              from f join l on {identity}
            """
        )
        by_name = {str(r.get('snapshot_label') or ''): dict(r) for r in labels}
        final_rows = int((by_name.get('final_ab') or {}).get('rows') or 0)
        learning_rows = int((by_name.get('learning_all') or {}).get('rows') or 0)
        overlap_rows = int(pair.get('overlap_rows') or 0)
        print(
            'STORAGE_REALTIME_LABEL_TABLE='
            f"name:{table} total_bytes:{int(relation.get('total_bytes') or 0)} "
            f"heap_bytes:{int(relation.get('heap_bytes') or 0)} "
            f"index_bytes:{int(relation.get('index_bytes') or 0)} "
            f"final_rows:{final_rows} learning_rows:{learning_rows} "
            f"overlap_rows:{overlap_rows} final_only:{max(0,final_rows-overlap_rows)} "
            f"learning_only:{max(0,learning_rows-overlap_rows)} "
            f"overlap_races:{int(pair.get('overlap_races') or 0)} "
            f"equal_payload:{int(pair.get('equal_payload_rows') or 0)} "
            f"different_payload:{int(pair.get('different_payload_rows') or 0)} "
            f"min_abs_seconds:{pair.get('min_abs_seconds')} "
            f"max_abs_seconds:{pair.get('max_abs_seconds')} "
            f"avg_abs_seconds:{pair.get('avg_abs_seconds')}"
        )
        for row in labels:
            print(
                'STORAGE_REALTIME_LABEL_DETAIL='
                f"table:{table} label:{row.get('snapshot_label')} "
                f"rows:{int(row.get('rows') or 0)} races:{int(row.get('races') or 0)} "
                f"min_date:{row.get('min_date')} max_date:{row.get('max_date')}"
            )
    print('STORAGE_REALTIME_LABEL_MATRIX_RESULT=PASS_READ_ONLY')


if __name__ == '__main__':
    main()
