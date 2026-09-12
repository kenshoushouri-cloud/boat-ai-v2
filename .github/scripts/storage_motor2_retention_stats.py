from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

OUT = Path("motor2-retention-stats.json")

SQL = r"""
WITH scoped AS (
  SELECT s.race_id,s.race_date,s.ticket,s.snapshot_key,s.snapshot_at,r.deadline_at
  FROM v2_v24_motor2_forward_shadow s
  JOIN v2_races r ON r.race_id=s.race_id
  WHERE s.run_class='final'
    AND s.window_name='final'
    AND s.race_date < (now() AT TIME ZONE 'Asia/Tokyo')::date
    AND r.deadline_at IS NOT NULL
), generations AS (
  SELECT race_id,race_date,snapshot_key,deadline_at,
         count(*) AS row_count,
         count(DISTINCT ticket) AS ticket_count,
         max(snapshot_at) AS last_snapshot_at
  FROM scoped
  GROUP BY race_id,race_date,snapshot_key,deadline_at
), valid AS (
  SELECT * FROM generations
  WHERE row_count=120 AND ticket_count=120 AND last_snapshot_at<=deadline_at
), chosen AS (
  SELECT race_id,race_date,snapshot_key,last_snapshot_at,deadline_at
  FROM (
    SELECT v.*,row_number() OVER (
      PARTITION BY race_id ORDER BY last_snapshot_at DESC,snapshot_key DESC
    ) AS rn
    FROM valid v
  ) x
  WHERE rn=1
), marked AS (
  SELECT s.*,
         c.snapshot_key AS chosen_snapshot_key,
         (c.race_id IS NOT NULL AND s.snapshot_key=c.snapshot_key) AS chosen_row,
         (c.race_id IS NOT NULL AND s.snapshot_key<>c.snapshot_key) AS older_row
  FROM scoped s
  LEFT JOIN chosen c ON c.race_id=s.race_id
)
SELECT
  count(*)::bigint AS scoped_rows,
  count(DISTINCT race_id)::bigint AS scoped_races,
  count(*) FILTER (WHERE chosen_row)::bigint AS chosen_rows,
  count(*) FILTER (WHERE older_row)::bigint AS older_rows,
  count(DISTINCT race_id) FILTER (WHERE chosen_row)::bigint AS eligible_races,
  count(DISTINCT race_id) FILTER (WHERE chosen_snapshot_key IS NULL)::bigint AS protected_races,
  pg_total_relation_size('v2_v24_motor2_forward_shadow')::bigint AS relation_bytes
FROM marked
"""


def main() -> None:
    url=os.getenv('DATABASE_URL')
    if not url:
        raise SystemExit('DATABASE_URL is required')
    with psycopg.connect(url,row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute("SET LOCAL statement_timeout='120s'")
        row=dict(conn.execute(SQL).fetchone())
    eligible=int(row['eligible_races'] or 0)
    chosen=int(row['chosen_rows'] or 0)
    if chosen != eligible*120:
        raise SystemExit('fail closed: chosen generation is not 120 rows per eligible race')
    scoped=int(row['scoped_rows'] or 0)
    older=int(row['older_rows'] or 0)
    row['older_share_pct']=round(older/scoped*100,6) if scoped else 0.0
    row['mutation_performed']=False
    OUT.write_text(json.dumps(row,indent=2,default=str)+'\n',encoding='utf-8')
    for k,v in row.items():
        print(f'MOTOR2_RETENTION_{k.upper()}={v}')
    print('MOTOR2_RETENTION_STATS_RESULT=PASS_READ_ONLY')


if __name__=='__main__':
    main()
