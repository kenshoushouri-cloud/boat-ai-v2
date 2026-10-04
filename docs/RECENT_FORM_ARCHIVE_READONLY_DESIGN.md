# Recent Form Archive — Read-only Design

## Scope / protection
- Source: `postgres-hobby-fullhistory-candidate-v4.public.v2_race_entries`
- Target archive service: `postgres-history-archive`
- This phase is **read-only**: no archive write, source cleanup, cutover, Railway resource creation, variable listing, Railway Agent/AI.
- Source query settings: `default_transaction_read_only=on`, `max_parallel_workers_per_gather=0`, bounded `statement_timeout`.

## Row identity
Archive row identity is **`(race_id, lane)`**.

Before any archive write, the read-only audit must PASS all of:
- `race_id IS NOT NULL`
- `lane IS NOT NULL`
- `count(*) = count(distinct (race_id,lane))` for rows where `recent_form IS NOT NULL`

Planned archive key: `PRIMARY KEY (race_id, lane)`.

## Exact row count
The archive set is exactly:
```sql
SELECT count(*) AS archive_rows
FROM public.v2_race_entries
WHERE recent_form IS NOT NULL;
```

Latest validated preflight observation: **425,772 rows**. This is not a fixed value; refresh immediately before any write.

## Deterministic payload checksum
Use PostgreSQL built-in MD5 only; no extension install is required.

```sql
WITH x AS (
  SELECT
    race_id,
    lane,
    md5(jsonb_build_array(race_id, lane, recent_form)::text) AS row_md5
  FROM public.v2_race_entries
  WHERE recent_form IS NOT NULL
)
SELECT
  count(*) AS row_count,
  md5(string_agg(row_md5, '' ORDER BY race_id, lane)) AS payload_md5
FROM x;
```

Reason:
- `jsonb` text is canonicalized by PostgreSQL.
- `jsonb_build_array` avoids delimiter ambiguity.
- explicit `ORDER BY race_id,lane` makes the aggregate deterministic.
- about 32 bytes × row_count are aggregated, so network transfer of the ~Recent Form payload is unnecessary.

## Restore verification
After a future archive write, run the same identity/count/checksum query against the archive table and require:
1. source archive_rows = archive archive_rows
2. source payload_md5 = archive payload_md5
3. archive key null count = 0
4. archive duplicate `(race_id,lane)` count = 0

Only after all four PASS may source cleanup be considered.

## Archive capacity estimate
Read-only planning inputs observed on 2026-10-05:
- live archive disk usage: **0.523173888 GB**
- latest validated compact-preflight reclaim bound: **810,287,104 bytes (~0.810287104 GB)**

Use the reclaim amount as a deliberately conservative upper bound for archive growth until a fresh payload-size audit is run:
- projected archive disk <= **1.333460992 GB**
- headroom under 5 GB >= **3.666539008 GB**

The actual archive addition should be lower than this bound because reclaim includes source relation/TOAST effects, not only the payload stored in a narrow archive table.

Before any write, refresh:
```sql
SELECT
  count(*) FILTER (WHERE recent_form IS NOT NULL) AS rows,
  coalesce(sum(pg_column_size(recent_form)) FILTER (WHERE recent_form IS NOT NULL),0) AS payload_bytes
FROM public.v2_race_entries;
```
and re-read archive disk usage.

## PASS gate for the next phase
The design is complete. The next step is a **single low-resource read-only audit** that returns fresh:
- key null count
- exact row count
- distinct key count
- deterministic payload_md5
- payload_bytes
- archive current disk usage
- conservative projected archive disk usage

No archive write is authorized by that audit.
