from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from storage_motor2_retention_stats import SQL as RETENTION_SQL

OUT_DIR = Path(os.getenv("MOTOR2_DUP_ARCHIVE_DIR", "motor2-duplicate-archive"))
ARCHIVE_PATH = OUT_DIR / "motor2_exact_duplicate_rows.jsonl.gz"
MANIFEST_PATH = OUT_DIR / "manifest.json"

CANDIDATE_SQL = r"""
WITH base AS (
    SELECT
        s.*,
        to_jsonb(s) - ARRAY[
            'id','snapshot_key','snapshot_at','created_at','updated_at'
        ]::text[] AS payload
    FROM v2_v24_motor2_forward_shadow s
    WHERE s.run_class = 'final'
      AND s.window_name = 'final'
      AND s.race_date < (now() AT TIME ZONE 'Asia/Tokyo')::date
), ordered AS (
    SELECT
        base.*,
        lead(id) OVER w AS next_id,
        lead(payload) OVER w AS next_payload,
        lead(evaluated_at) OVER w AS next_evaluated_at
    FROM base
    WINDOW w AS (
        PARTITION BY race_id, ticket, run_class, window_name
        ORDER BY snapshot_at, id
    )
), candidate AS (
    SELECT id
    FROM ordered
    WHERE next_id IS NOT NULL
      AND evaluated_at IS NOT NULL
      AND next_evaluated_at IS NOT NULL
      AND payload = next_payload
)
SELECT s.*
FROM v2_v24_motor2_forward_shadow s
JOIN candidate c ON c.id = s.id
ORDER BY s.id
"""

SUMMARY_SQL = r"""
SELECT
    count(*)::bigint AS total_rows,
    min(race_date) AS min_race_date,
    max(race_date) AS max_race_date,
    pg_total_relation_size('v2_v24_motor2_forward_shadow')::bigint AS relation_bytes,
    pg_relation_size('v2_v24_motor2_forward_shadow')::bigint AS heap_bytes,
    pg_indexes_size('v2_v24_motor2_forward_shadow')::bigint AS index_bytes
FROM v2_v24_motor2_forward_shadow
"""


def canonical_line(row: dict) -> bytes:
    return (
        json.dumps(
            row,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )
        + "\n"
    ).encode("utf-8")


def main() -> None:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is required")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    id_hash = hashlib.sha256()
    content_hash = hashlib.sha256()
    count = 0
    min_id = None
    max_id = None
    min_date = None
    max_date = None

    with psycopg.connect(url, row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '120s'")
        conn.execute("SET LOCAL temp_file_limit = '128MB'")

        summary = conn.execute(SUMMARY_SQL).fetchone()
        retention = dict(conn.execute(RETENTION_SQL).fetchone())
        retention_scoped = int(retention["scoped_rows"] or 0)
        retention_older = int(retention["older_rows"] or 0)
        retention_eligible = int(retention["eligible_races"] or 0)
        retention_chosen = int(retention["chosen_rows"] or 0)
        if retention_chosen != retention_eligible * 120:
            raise SystemExit("fail closed: chosen generation is not 120 rows per eligible race")
        retention["older_share_pct"] = (
            round(retention_older / retention_scoped * 100, 6)
            if retention_scoped else 0.0
        )

        with gzip.open(ARCHIVE_PATH, "wb", compresslevel=9, mtime=0) as gz:
            with conn.cursor(name="motor2_exact_duplicate_archive") as cur:
                cur.itersize = 1000
                cur.execute(CANDIDATE_SQL)
                for row in cur:
                    row = dict(row)
                    row_id = int(row["id"])
                    race_date = str(row.get("race_date") or "")
                    line = canonical_line(row)
                    gz.write(line)
                    id_hash.update(f"{row_id}\n".encode("ascii"))
                    content_hash.update(line)
                    count += 1
                    min_id = row_id if min_id is None else min(min_id, row_id)
                    max_id = row_id if max_id is None else max(max_id, row_id)
                    if race_date:
                        min_date = race_date if min_date is None else min(min_date, race_date)
                        max_date = race_date if max_date is None else max(max_date, race_date)

    manifest = {
        "contract": "motor2_adjacent_exact_duplicate_v1",
        "scope": {
            "run_class": "final",
            "window_name": "final",
            "completed_before_jst_today": True,
            "current_and_next_evaluated_required": True,
            "adjacent_only": True,
            "payload_excludes_only": [
                "id",
                "snapshot_key",
                "snapshot_at",
                "created_at",
                "updated_at",
            ],
        },
        "candidate_count": count,
        "candidate_id_sha256": id_hash.hexdigest(),
        "candidate_content_sha256": content_hash.hexdigest(),
        "candidate_min_id": min_id,
        "candidate_max_id": max_id,
        "candidate_min_race_date": min_date,
        "candidate_max_race_date": max_date,
        "source_total_rows": int(summary["total_rows"]),
        "source_min_race_date": str(summary["min_race_date"] or ""),
        "source_max_race_date": str(summary["max_race_date"] or ""),
        "source_relation_bytes": int(summary["relation_bytes"]),
        "source_heap_bytes": int(summary["heap_bytes"]),
        "source_index_bytes": int(summary["index_bytes"]),
        "retention_contract": "latest_complete_predeadline_generation_v1",
        "retention_stats": {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in retention.items()},
        "archive_file": ARCHIVE_PATH.name,
        "mutation_performed": False,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"MOTOR2_EXACT_DUP_CANDIDATES={count}")
    print(f"MOTOR2_EXACT_DUP_ID_SHA256={manifest['candidate_id_sha256']}")
    print(f"MOTOR2_EXACT_DUP_CONTENT_SHA256={manifest['candidate_content_sha256']}")
    print(f"MOTOR2_EXACT_DUP_DATE_RANGE={min_date or '-'}..{max_date or '-'}")
    print(f"MOTOR2_SOURCE_TOTAL_ROWS={manifest['source_total_rows']}")
    print(f"MOTOR2_SOURCE_RELATION_BYTES={manifest['source_relation_bytes']}")
    print(f"MOTOR2_RETENTION_SCOPED_ROWS={retention_scoped}")
    print(f"MOTOR2_RETENTION_SCOPED_RACES={int(retention['scoped_races'] or 0)}")
    print(f"MOTOR2_RETENTION_ELIGIBLE_RACES={retention_eligible}")
    print(f"MOTOR2_RETENTION_CHOSEN_ROWS={retention_chosen}")
    print(f"MOTOR2_RETENTION_OLDER_ROWS={retention_older}")
    print(f"MOTOR2_RETENTION_OLDER_SHARE_PCT={retention['older_share_pct']}")
    print(f"MOTOR2_RETENTION_PROTECTED_RACES={int(retention['protected_races'] or 0)}")
    print("MOTOR2_EXACT_DUP_ARCHIVE_RESULT=PASS_READ_ONLY")


if __name__ == "__main__":
    main()
