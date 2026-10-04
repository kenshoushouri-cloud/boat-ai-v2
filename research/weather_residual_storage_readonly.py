# -*- coding: utf-8 -*-
"""Read-only storage audit for wave/wind/residual-named derived relations."""
import os
import psycopg

def main() -> None:
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db) as conn:
        conn.execute("set default_transaction_read_only=on")
        with conn.cursor() as cur:
            cur.execute("""
                select c.relname,
                       c.relkind,
                       pg_total_relation_size(c.oid)::bigint,
                       pg_relation_size(c.oid)::bigint,
                       pg_indexes_size(c.oid)::bigint
                from pg_class c
                join pg_namespace n on n.oid=c.relnamespace
                where n.nspname='public'
                  and c.relkind in ('r','p')
                  and (
                    c.relname ilike '%wave%'
                    or c.relname ilike '%wind%'
                    or c.relname ilike '%residual%'
                  )
                order by pg_total_relation_size(c.oid) desc,c.relname
            """)
            rows=cur.fetchall()
    total=0
    for name,kind,total_b,heap_b,idx_b in rows:
        total += int(total_b or 0)
        print(f"DERIVED_REL|{name}|kind={kind}|total_bytes={int(total_b or 0)}|heap_bytes={int(heap_b or 0)}|index_bytes={int(idx_b or 0)}")
    print(f"DERIVED_MATCH_COUNT={len(rows)}")
    print(f"DERIVED_MATCH_TOTAL_BYTES={total}")
    print(f"DERIVED_MATCH_TOTAL_MB={total/1_000_000:.3f}")
    print("REJECTED_WAVE_RESIDUAL_PERSISTENCE=READ_ONLY_IN_MEMORY")
    print("REJECTED_WIND_RESIDUAL_PERSISTENCE=READ_ONLY_IN_MEMORY")
    print("RAW_WEATHER_TABLE_EXCLUDED=1")
    print("DB_READ_ONLY=1 DB_WRITE=0 RESULT_ODDS_PAYOUT_READ=0")

if __name__ == "__main__":
    main()
