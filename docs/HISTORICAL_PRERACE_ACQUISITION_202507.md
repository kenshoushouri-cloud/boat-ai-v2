# Historical pre-race acquisition — Phase 1 / 2025-07

Status: `APPROVED / RAW_ACQUISITION_ONLY / NO_DB_WRITE / NO_MODEL_CHANGE`

## User-approved policy

Historical missing-data acquisition is approved.

For historical reconstruction, the project will accept only sources that represent information available before the target race deadline. Historical values are not treated as prospective Forward evidence; they are a matched-contract backtest resource.

## Source priority

1. **BOAT RACE official**
   - race-card / program PDFs and official download services;
   - racer term statistics.
2. **BoatraceCSV pre-race archive**
   - Race Cards;
   - Recent National Form;
   - Recent Local Form;
   - Waku10;
   - Motor Stats;
   - Race Title / deadline metadata.
3. **艇国データバンク**
   - supplemental cross-check and fields not reasonably obtained from official downloads;
   - respect its published access rules;
   - do not bulk-download program/result/racer-term data there when the site directs users to BOAT RACE official downloads.

## Phase 1 boundary

Acquire **2025-07-01 through 2025-07-31 only**.

This phase:
- downloads raw pre-race archive files;
- preserves raw bytes;
- records SHA256 per file;
- records row counts and missing/error days;
- creates a manifest;
- does not normalize;
- does not write PostgreSQL;
- does not read results, payouts or odds;
- does not run a backtest.

Maximum acquisition range is hard-coded to 31 days per run to keep work restartable and timeout-safe.

## Deadline policy

A field can enter the historical matched-contract dataset only when its source semantics support availability before the target race deadline.

Examples:
- official / archived race card: eligible as pre-race;
- recent form carried in a pre-race program source: eligible as pre-race;
- deadline-stamped preview: eligible only when acquisition timestamp is before deadline;
- values reconstructed from post-result state without contemporaneous provenance: not eligible for the matched-contract dataset.

## Next phases

After Phase 1 coverage is measured:
1. fill Race Card gaps from official BOAT RACE historical program/PDF sources;
2. add deadline-stamped preview sources where historical coverage exists;
3. normalize to a separate historical staging artifact/schema;
4. cross-check selected values with 艇国DB under its access rules;
5. only after source/provenance checks, propose the Production DB import separately.

`2025_07_FIRST / RAW_ONLY / SOURCE_HASHED / DEADLINE_PRE_RACE_POLICY / NO_RESULTS / NO_DB_WRITE / PURCHASE_FALSE`
