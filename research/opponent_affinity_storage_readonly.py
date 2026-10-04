# -*- coding: utf-8 -*-
"""Read-only storage audit for opponent/course/affinity-derived relations."""
import os
import psycopg

PATTERNS = ("%opponent%", "%racer_course%", "%affinity%", "%composition%")

def main() -> None:
    db=(os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db) as conn:
        conn.execute("set default_transaction_read_only=on")
        with conn.cursor() as cur:
            cur.execute("""
                select c.relname,
                       pg_total_relation_size(c.oid)::bigint,
                       pg_relation_size(c.oid)::bigint,
                       pg_indexes_size(c.oid)::bigint
                from pg_class c
                join pg_namespace n on n.oid=c.relnamespace
                where n.nspname='public'
                  and c.relkind in ('r','p')
                  and (
                    c.relname ilike %s or c.relname ilike %s
                    or c.relname ilike %s or c.relname ilike %s
                  )
                order by pg_total_relation_size(c.oid) desc,c.relname
            """, PATTERNS)
            rows=cur.fetchall()
    total=0
    for name,total_b,heap_b,idx_b in rows:
        total += int(total_b or 0)
        print(f"REL|{name}|total_bytes={int(total_b or 0)}|heap_bytes={int(heap_b or 0)}|index_bytes={int(idx_b or 0)}")
    print(f"MATCH_COUNT={len(rows)}")
    print(f"MATCH_TOTAL_BYTES={total}")
    print(f"MATCH_TOTAL_MB={total/1_000_000:.3f}")
    print("REJECTED_INDIVIDUAL_AFFINITY_PERSISTENCE=NONE_READ_ONLY_OOS")
    print("OPPONENT_PRESSURE_SEPARATE_RESEARCH_DEPENDENCY=1")
    print("RACER_COURSE_BASELINE_INPUT=1")
    print("DB_READ_ONLY=1 DB_WRITE=0 RESULT_ODDS_PAYOUT_READ=0")

if __name__ == "__main__":
    main()
