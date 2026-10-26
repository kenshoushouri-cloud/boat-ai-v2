# V5 — 2025-07-01 through current: verify storage before prediction/backtest
Status: AUDIT-FIRST / NO DATA REWRITE / NO BUY. 2026-10-26 JST.
User priority: do not repeatedly repair backtests caused by inconsistent
historical and realtime storage. VERIFY, THEN FIX uniformly, THEN backtest.

## Single target contract / 13 families
**Scope decision 2026-10-26 19:19 JST: ONLY V5 SHARED data (`boat_data_stage.*` physical tables), not complete audit/repair of unreliable historical `public.v2_*` sources.** Source aliases `public.v2_*` are lineage needed for the already-approved staged delta, NOT proof that values are correct.
Current logical `boat_data.*` objects are read-only-compatible live VIEWs
pointing at legacy sources, **not** the 13 physical V5 writes.
Proposed identical 13 physical locations: `boat_data_stage.*`, copied with
existing stage migration (including protected preexisting `venues`).
Mappings and source-specific evidence rules are controlled in
`boat_shared_storage_contract.RELATIONS`. Never silently union the distinct
`boat_history_archive` database as if it were the local DB.
Storage unification for V5 means one named schema/adapter with documented
provenance, NOT forced destructive copying/merging of every historic archive.

## Gates in order (cannot skip)
1. **Catalog/route audit, minimal DB load:** completed 2026-10-26 19:19 JST with 13/13 `CATALOG_SHAPE_OK_PERIOD_NOT_AUDITED` from user's read-only screenshot (after earlier separate timeout). This is structural evidence only. Audit SQL:
   `deploy/conoha/v5_storage_13_family_catalog_readonly_20261026.sql`.
   Reports for all 13: source physical table, current live VIEW, stage
   physical table, ordered column type/nullability shape, primary key,
   candidate race/date/snapshot timestamp fields, original stage origin
   marker. Report `HOLD_*` rows, do not modify. This only certifies
   *structural* parity; not whether each month is populated.
2. **Stage-only index/date preflight then period coverage, after planned night sync:** stage-only index/date catalog preflight `deploy/conoha/v5_shared_stage_13_index_preflight_readonly_20261026.sql` completed at 19:32 JST (13 rows, no monthly scan). Still verify exact query plans and month coverage. Only for `boat_data_stage.*` physical tables, no legacy source scans. Then:
   2025-07 through current month inclusive. On staged physical data only,
   batch one family/month (or index-range) with bounded statement time,
   read-only, low work_mem; do not do a full 13-way join. Count row totals,
   distinct races/lanes/PKs, duplicate keys, first/last race date, valid
   snapshot capture timestamps, source-version distribution. For families
   without `race_date`, use an indexed race_id or suitable captured timestamp
   only after confirming its actual type/semantics in Gate 1. Distinguish
   genuine period data gaps from expected no-race/no-live-capture periods.
   Never assume historical realtime snapshots exist in every month.
3. **Field contract/semantics audit by month and 13-family join keys:**
   Evaluate staged shared records for six lanes per race where expected,
   `racer_number` (integer) vs legacy `racer_no` (possibly SQL NULL),
   motor/boat number parsing, all 13 stats' NULL rates and outlier scales,
   `recent_form` JSON shape, odds ticket/payout units, exhibition/weather
   timestamp timezone and sampling versions, provenance fields; identify
   schema/version change-points. NULL is not zero, and blank alias is not
   evidence of an incorrect canonical integer identity. Compare numeric
   rates to per-column documented domains; universal 0..100 is not enough.
4. **Fix in a separate V5 shared normalization layer first** (versioned per-family
   adapter or clean staging view, proven by tests). Do not rewrite old
   `public.v2_*` sources or overwrite captured pre-deadline snapshots.
   Fix mappings/types/aliases/date parsing with explicit origin fields;
   quarantine invalid/missing/unknown data, and document original values.
   Existing stage sync is a copy of old values, NOT a truth/quality repair. Never let provenance from old values automatically authorize backtest or overwrite post-normalization curated values. For actual stage-physical transformations, require protected rollback,
   independent after-write parity, idle collector window and new approval.
   Do not relabel mutable history as immutable first observation.
5. **Acceptance gates before 2025-07+ backtest:** verified per-month matrix
   for all 13 families (including explicitly marked absent/unavailable),
   one canonical schema contract, stable keys/types/units, recorded
   chronology/provenance eligibility per feature, stage synchronized,
   tests and sample races verified, long-running read workload budgeted.
   Only backtest independently provable as-of subset, with HOLD reasons for
   others; report sample size, not fabricated all-period ROI. BUY OFF.

## Night safety / no duplicate job
- Existing single stage11 delta timer for 2026-10-27 03:05 JST remains
  untouched. Never start a duplicate delta or blind all-history scan.
- The catalog audit is safe to run now (catalog metadata only). Monthly
  physical-table sampling waits for synchronization verdict and index/
  budget review, and never competes with 5-minute odds/exhibition capture.
- Backup expansion is user-deferred, therefore **no destructive cleanup
  or rewrite** without separate restore protection and explicit consent.
- No Railway access. No writer cutover. Do not reboot ConoHa tonight.

## Acceptance of shared-only approach (2026-10-26)
- Treat `boat_data_stage` as **the only V5 historical audit dataset** after verifying the 03:05 scheduled delta. The current `boat_data` names are legacy-backed VIEWs, so do not mistake them for independent cleaned V5 data.
- Old data consulted **only** for an identified gap that cannot be resolved within the staged common set, with explicit provenance and no broad cleanup. External official source verification preferred for suspected wrong records.
- Report `AVAILABLE / VERIFIED / NULL_MISSING / SEMANTIC_MISMATCH / SOURCE_UNPROVEN / MONTH_NOT_CAPTURED` per shared family and period. V5 backtest uses VERIFIED independently eligible time-safe subset only; other rows HOLD.
- A 13/13 catalog match confirms current columns and keys, **not** 2025-07 to current coverage, 13-value correctness, or original as-of captures.

## Verified stage index preflight — 2026-10-26 19:32 JST
- User screenshot: 13 rows, ROLLBACK, read-only completion marker. Visible metadata sizes: trifecta_odds 1826 MB, odds_snapshots 779 MB, racer_results 256 MB, weather_snapshots 191 MB, racer_course_stats_snapshots 89 MB, races 19 MB, results 32 MB, venues 48 KB. Upper three rows (entries/entry_snapshots/exhibition_snapshots) not fully visible, so need actual evidence before assigning their scan methods.
- Daytime multi-GB full scans are forbidden. After stage11, prefer indexed bounded monthly scan starting with races/race_date, then independently verify each other family. Even if 13 family schemas/indexes match, copied old values cannot be assumed true.
