# Odds-only `learning_all` design — 2026-09-12

Research design only. This document does **not** implement, merge, deploy, enable, disable, or alter any Production collector, Railway variable, Cron, model coefficient, LINE path, or database row.

## Why this design exists

Capacity research found two facts that must both be preserved:

1. `learning_all` duplicates almost all realtime identity coverage and adds about `10,890.71` logical rows per completed day across six realtime tables.
2. `learning_all` odds are part of the current effective Production market-observation cadence because `_fetch_previous_odds(rid)` is cross-label. A later `final_ab` row frequently uses the preceding `learning_all` odds as its `prev_odds` / previous market rank, and v22 scores derived drift/steam flags.

Therefore a full learning pause is not a cleanup-only action. The narrow research target is to preserve the `learning_all` **odds** cadence while avoiding duplicate `learning_all` beforeinfo-derived writes.

## Current collector seam

`v21_realtime_collector_pg_safe.py` currently processes each target race in two sequential blocks:

1. beforeinfo fetch + saves:
   - weather
   - exhibition
   - entry snapshot
   - race condition
   - racer condition
2. odds3t fetch + complete-snapshot validation + odds save

The odds block is independent after beforeinfo processing. `_save_complete_odds()` still calls the existing cross-label `legacy._fetch_previous_odds(rid)`.

This separation means an odds-only mode can be designed without changing odds parsing, odds completeness requirements, cross-label previous-odds lookup, decision-target files, or Production v22 logic.

## Proposed default-off contract

A future implementation Draft may introduce a collector flag such as `ODDS_ONLY_MODE`, default `0`.

The learning wrapper may map an explicitly set research variable such as `LEARNING_ODDS_ONLY=1` to `ODDS_ONLY_MODE=1` for the learning subprocess only.

Required behavior when `ODDS_ONLY_MODE=0`:

- byte-for-byte-equivalent control flow to the current collector apart from observability logging;
- fetch/save weather, exhibition, entry, race condition, racer condition, and odds exactly as today;
- no Production behavior change.

Required behavior when `ODDS_ONLY_MODE=1`:

- retain the same target-date and 30-minute deadline-window selection;
- retain `COLLECT_SCOPE=all` for learning;
- retain label `learning_all`;
- retain the separate learning target-race-id file;
- skip the `beforeinfo` HTTP request entirely;
- skip all learning-label weather/exhibition/entry/race-condition/racer-condition writes;
- still fetch official `odds3t` for every target race;
- retain exact dynamic `120/60/24` fail-closed validation;
- retain `_save_complete_odds()` unchanged;
- retain cross-label `_fetch_previous_odds(rid)` semantics unchanged;
- retain current sleep/cadence behavior;
- never call v22, notifier, LINE, purchase, or Production decision code.

## Production final-check isolation

`cron-final-check` must remain behaviorally untouched.

The design must ensure:

- `run_final_pg.py` does not set odds-only mode;
- `v25_final_realtime_pipeline_pg.py` does not enable odds-only mode;
- final collector default remains full realtime collection;
- final `SNAPSHOT_LABEL=final_ab` path remains unchanged;
- `TARGET_ID_SCOPE=candidates` continues to narrow only decision IDs, not collection coverage.

A future implementation test must fail if the final chain can accidentally inherit or enable learning odds-only behavior.

## Expected capacity/load effect

Current `learning_all` logical tuple payload:

- odds: `75,876,808` bytes (~73.63%)
- non-odds: `27,174,160` bytes (~26.37%)

Latest seven completed days, non-odds learning only:

- `10,912` rows total (~`1,558.9/day`)
- `4,575,256` logical tuple bytes total (~`653,608 bytes/day`, ~0.62 MiB/day)

This is not a large standalone volume-saving lever. The more useful operational benefit may be removal of duplicated beforeinfo HTTP requests, parsing, and five non-odds snapshot write paths.

No proportional Railway-volume shrink may be inferred from these logical tuple numbers.

## Why odds must remain in the first design

A full pause or an odds-free learning mode changes the observation sequence feeding `final_ab.prev_odds`.

Read-only evidence:

- later-final rows after a learning observation: `188,319`
- later-final rows whose previous odds/rank match learning: `188,080` (~99.87%)
- direct matches within 180 seconds: `177,186`
- latest-seven-day direct matches: `31,617`
- counterfactual one-step proxy rows with changed drift/steam movement score if the learning hop is removed: `15,419`
- latest-seven-day proxy changes: `10,805`

Accordingly, the first capacity-safe design must preserve the odds collection cadence. Changing the previous-odds semantics is a separate model-input experiment.

## Required tests for any implementation Draft

A future unmerged Draft implementation should include pure/static tests proving:

- default `ODDS_ONLY_MODE=0` preserves the full collector path;
- `ODDS_ONLY_MODE=1` skips every beforeinfo fetch/save function;
- odds fetch still runs for every target race;
- `_save_complete_odds()` and `_fetch_previous_odds()` behavior are unchanged;
- learning wrapper is the only runtime path allowed to opt in;
- final pipeline cannot opt in through defaults;
- no v22/LINE/purchase wiring is introduced;
- `COLLECT_SCOPE=all`, deadline-window behavior, and learning target-file isolation remain unchanged.

No Production live A/B test should be performed merely because the static tests pass. Deployment/enablement remains a separate approval gate.

## Rollback shape if later approved

The proposed mode is intentionally variable-gated so a later authorized rollout could be reversed by restoring `LEARNING_ODDS_ONLY=0` while leaving odds history and final-check unchanged.

That reversibility does not make activation non-Production: changing the Railway variable or collection behavior still requires explicit approval.

## Approval boundary

Allowed now:

- code reading;
- pure tests/design work on an unmerged research branch;
- Draft PR implementation isolated from main;
- read-only capacity/load estimates.

Not authorized by this design:

- merge to main;
- Railway variable creation/change;
- Cron/service change;
- Production activation;
- full `learning_all` pause;
- label-scoped previous-odds rewrite;
- historical row deletion;
- VACUUM/physical rewrite.

Current design gate:

`ODDS_ONLY_DESIGN_FEASIBLE / PRESERVE_LEARNING_ODDS_CADENCE / SKIP_NON_ODDS_BEFOREINFO_ONLY / DEFAULT_OFF / FINAL_CHAIN_UNCHANGED / CROSS_LABEL_PREVIOUS_ODDS_UNCHANGED / EXPECTED_NON_ODDS_REDUCTION_1559_ROWS_PER_DAY / EXPECTED_LOGICAL_TUPLE_REDUCTION_0_62MIB_PER_DAY / IMPLEMENTATION_DRAFT_ALLOWED / NO_MERGE / NO_DEPLOY / NO_RAILWAY_CHANGE`
