# -*- coding: utf-8 -*-
"""Read-only Production-schema audit for completed-learning archive identities.

The future cold-archive contract may only rely on keys that are actually enforced
as unique in the current Production schema. Catalog SELECTs only; no mutation.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db_pg import fetch_all

EXPECTED = {
    "v2_realtime_odds_snapshots": ("race_id", "snapshot_label", "ticket"),
    "v2_realtime_weather_snapshots": ("race_id", "snapshot_label"),
    "v2_realtime_exhibition_snapshots": ("race_id", "snapshot_label", "lane"),
    "v2_realtime_entry_snapshots": ("race_id", "snapshot_label", "lane"),
    "v2_realtime_race_condition_snapshots": ("race_id", "snapshot_label"),
    "v2_realtime_racer_condition_snapshots": ("race_id", "snapshot_label", "lane"),
}


def unique_indexes(table: str) -> list[dict]:
    return [
        dict(r)
        for r in fetch_all(
            """
            select ci.relname as index_name,
                   i.indisprimary,
                   i.indisunique,
                   i.indisvalid,
                   i.indisready,
                   array_agg(a.attname order by u.ord)
                     filter (where u.ord <= i.indnkeyatts) as key_columns
              from pg_index i
              join pg_class ct on ct.oid=i.indrelid
              join pg_namespace n on n.oid=ct.relnamespace
              join pg_class ci on ci.oid=i.indexrelid
              cross join lateral unnest(i.indkey) with ordinality as u(attnum,ord)
              left join pg_attribute a
                on a.attrelid=i.indrelid and a.attnum=u.attnum
             where n.nspname='public'
               and ct.relname=%s
               and i.indisunique
             group by ci.relname,i.indisprimary,i.indisunique,i.indisvalid,i.indisready
             order by ci.relname
            """,
            (table,),
        )
    ]


def main() -> None:
    print("STORAGE_LEARNING_ARCHIVE_IDENTITY_MODE=READ_ONLY_CATALOG_NO_MUTATION")
    failed = []
    for table, expected in EXPECTED.items():
        indexes = unique_indexes(table)
        exact = [
            x for x in indexes
            if tuple(str(c) for c in (x.get("key_columns") or ())) == expected
            and bool(x.get("indisvalid"))
            and bool(x.get("indisready"))
        ]
        print(
            "STORAGE_LEARNING_ARCHIVE_IDENTITY="
            f"table:{table} expected:{','.join(expected)} "
            f"unique_indexes:{len(indexes)} exact_valid_ready_matches:{len(exact)} "
            f"match_names:{','.join(str(x.get('index_name')) for x in exact) if exact else '-'}"
        )
        for row in indexes:
            print(
                "STORAGE_LEARNING_ARCHIVE_UNIQUE_INDEX="
                f"table:{table} name:{row.get('index_name')} "
                f"columns:{','.join(str(c) for c in (row.get('key_columns') or ())) or '-'} "
                f"primary:{str(bool(row.get('indisprimary'))).lower()} "
                f"valid:{str(bool(row.get('indisvalid'))).lower()} "
                f"ready:{str(bool(row.get('indisready'))).lower()}"
            )
        if len(exact) != 1:
            failed.append(table)

    if failed:
        print("STORAGE_LEARNING_ARCHIVE_IDENTITY_RESULT=BLOCK_SCHEMA_IDENTITY_MISMATCH")
        raise SystemExit("archive identity contract mismatch: " + ",".join(failed))
    print("STORAGE_LEARNING_ARCHIVE_IDENTITY_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
