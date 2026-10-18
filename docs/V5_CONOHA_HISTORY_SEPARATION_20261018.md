# ConoHa 履歴保管庫と独立 V5 運用 — 2026-10-18
Status: **DESIGN / NO DATA MOVED**. Railway, ConoHa SQL, services, costs and V5 execution were not changed by this document.

## Decision
- V5 is independent of V4 runtime. Retire obsolete Railway V4 / history DB services **only after** independent archival coverage and backup restoration checks. Do not assume V4 Railway == ConoHa copies when direct comparison was unavailable.
- Store **2025-07-01 onward full raw historical records** separately from **V5 production data** on ConoHa, preferably a dedicated history database (reuse existing if fit), plus a separate restorable backup copy. Use PostgreSQL read-only access from V5 research/backtests; export/copy only needed dated features into V5. No blindly replicated multi-GB tables.
- Keep source identifiers, first-seen timestamps, snapshot label, provenance, original contents/hash where possible. Historical reconstructed exhibition, odds, weather and conditions are **NOT** verified as actually available before race cutoff; quarantine and exclude from real-as-of/forward/BUY until independent evidence.
- Backtests can read archive but must freeze model inputs before results; separate retrospective scenario ROI from truly observed predecision performance; preserve missing, F/L, VOID, refund, PENDING in settlement population.
- Separate logical databases alone are not disaster recovery. Retain dump + tested restore and obtain an off-VPS copy before deleting last Railway original. Never store LINE tokens, secrets, or dump files in GitHub.
- Budget priority: no Railway Agent/AI, no added always-on instances; avoid copying all archives into the lightweight V5 DB. V5 BUY remains HARD HOLD and needs a separate explicit approval.

## Observed state from this conversation (must recheck live)
- ConoHa has V4 recovery database (39 tables), independently created `/root/boatbackup/v4_full_20261018.dump`, restored and reconciled **13,640,730 rows across 39 tables** vs local V4 recovery. This proves *local* backup restore and row counts, **not** equality with offline Railway V4.
- V4 Railway candidate was Offline after disk-full failure, with ~4.99 GB used; do not delete until loss risk reviewed and archival data / backup off VPS confirmed.
- Railway V3 candidate + associated volume deleted after ConoHa restore and row-count matching.
- Historical exhibition/condition/weather V4-only rows were quarantined on ConoHa; V4 motor2 shadow delta saved to CSV. Preserve original snapshots without promoting late/rebuilt features to predecision proof.
- ConoHa has a history DB according to prior operator checks, but its **current DB name, schema, retention, raw-file coverage and V5 dependency are NOT yet audited**. Railway history archive (~2.34 GB at last measurement) must not be deleted until audited.

## Next ONE task
Run read-only ConoHa DB inventory (database names, estimated relation sizes, table names) and identify the actual history/production candidates. **No CREATE, DROP, ALTER, INSERT, COPY FROM, cluster restart, or Railway delete.**
Then separately check source-vs-archive coverage, external restore availability and any V5 connection dependencies. Only then implement read-only archive access and safe copies as needed.
