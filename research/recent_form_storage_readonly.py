# -*- coding: utf-8 -*-
"""Read-only capacity audit for v2_race_entries.recent_form."""
import os
import psycopg

def main() -> None:
    db = (os.getenv("DATABASE_URL") or "").strip()
    if not db:
        raise RuntimeError("DATABASE_URL required")
    with psycopg.connect(db) as conn:
        conn.execute("set default_transaction_read_only=on")
        with conn.cursor() as cur:
            cur.execute("""
                select
                  pg_total_relation_size('v2_race_entries')::bigint,
                  pg_table_size('v2_race_entries')::bigint,
                  pg_indexes_size('v2_race_entries')::bigint,
                  count(*)::bigint,
                  count(*) filter (
                    where recent_form is not null
                      and recent_form::text not in ('null','[]','{}','""','')
                  )::bigint,
                  coalesce(sum(pg_column_size(recent_form))
                    filter (where recent_form is not null),0)::bigint,
                  coalesce(avg(pg_column_size(recent_form))
                    filter (where recent_form is not null),0)::numeric(18,2),
                  coalesce(max(pg_column_size(recent_form))
                    filter (where recent_form is not null),0)::bigint
                from v2_race_entries
            """)
            total, table, idx, rows, recent_rows, recent_bytes, recent_avg, recent_max = cur.fetchone()

            cur.execute("""
                select
                  case when c.reltoastrelid = 0 then 0
                       else pg_total_relation_size(c.reltoastrelid)
                  end::bigint
                from pg_class c
                where c.oid='v2_race_entries'::regclass
            """)
            toast_bytes = int(cur.fetchone()[0] or 0)

    print(f"RFE_TOTAL_RELATION_BYTES={total}")
    print(f"RFE_TABLE_BYTES={table}")
    print(f"RFE_INDEX_BYTES={idx}")
    print(f"RFE_TOAST_TOTAL_BYTES={toast_bytes}")
    print(f"RFE_ROWS={rows}")
    print(f"RECENT_FORM_NONEMPTY_ROWS={recent_rows}")
    print(f"RECENT_FORM_COLUMN_BYTES={recent_bytes}")
    print(f"RECENT_FORM_COLUMN_MB={recent_bytes/1_000_000:.3f}")
    print(f"RECENT_FORM_AVG_BYTES={recent_avg}")
    print(f"RECENT_FORM_MAX_BYTES={recent_max}")
    print("DB_READ_ONLY=1 DB_WRITE=0 RESULT_ODDS_PAYOUT_READ=0")

if __name__ == "__main__":
    main()
