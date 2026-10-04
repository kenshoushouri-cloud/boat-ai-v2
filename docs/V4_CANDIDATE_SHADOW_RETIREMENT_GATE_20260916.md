# V4 candidate-shadow retirement gate — 2026-09-16

## Fresh override — 2026-09-21 12:42 JST

Current code Source of Truth is now `8867b77569d836b6c02a075fa6444550b1a46a6c`.

A fresh Railway Production config + natural-run audit reconfirmed that `v2_candidate_filter_shadow` is not retireable:

- `cron-window-morning`, `cron-window-day`, and `cron-window-night` all still source `boat-ai-v2@main`, start `python -u run_window_pipeline_pg.py`, expose candidate-shadow variable names, and have no staged config changes;
- `cron-nightly-results` still starts `python -u run_nightly_results_pg.py` and retains candidate-shadow evaluator/report variable names;
- no-Cron `test-beforeinfo-extra` still starts `python -u collect_candidate_filter_shadow_pg.py` directly and remains a repository-triggerable writer surface;
- current main still invokes the PRE collector, nightly evaluator, and V4 same-day S01-S05 legacy reader.

Natural 2026-09-21 runtime evidence:
- morning Production window: candidate-shadow enabled; collector invoked; `candidate_rows=0 / saved_rows=0`;
- day Production window: candidate-shadow enabled; collector invoked; `candidate_rows=7 / saved_rows=7`;
- formal V4 run `35549611949`: `legacy_shadow_rows=7`, `legacy_added_races=5`, `legacy_added_tickets=7`.

This gives same-day writer -> reader proof on current Production. The newly activated V4 fallback dispatcher has separately been audited and has no PostgreSQL/candidate-shadow dependency, so it neither creates nor clears this blocker.

Machine-readable snapshot:
`research/evidence/candidate_shadow_zero_consumer_gate_20260921.json`

The pure runtime inventory contract now treats both `candidate_shadow_writer` and `candidate_shadow_reader` capabilities as zero-consumer blockers. Its current-like fixture includes the Railway nightly reader and the GitHub V4 prospective-freeze reader, preventing a false PASS after writers disappear while readers still remain.

Current classification:
`ZERO_CONSUMER_NOT_REACHED / ACTIVE_WRITER_INVOCATION / SAME_DAY_7_ROW_WRITE / CURRENT_MAIN_V4_7_ROW_READ / NIGHTLY_EVALUATOR_PATH_PRESENT / TEST_BEFOREINFO_EXTRA_WRITER_SURFACE / NO_DELETE / NO_MIGRATION / NO_VACUUM / PURCHASE_FALSE`

The older 2026-09-16 sections below remain useful as historical rationale, but any SHA/runtime statement there is superseded by this override.


Status: `RESEARCH_ONLY / CURRENT_MAIN_DEPENDENCY_PRESENT / ZERO_CONSUMER_BLOCKED / NO_PRODUCTION_MUTATION`

This document freezes the current dependency and retirement ordering for `v2_candidate_filter_shadow` before any archive/delete decision. It does not disable a writer, change a Railway service, alter the V4 candidate contract, delete data, or authorize Production migration. `purchase_action=false` remains mandatory.

## 1. Source-of-truth boundary

Current GitHub `main` at this review remains:

`61f7d6e75629ffb549a583f00bfd5dd58c186a71`

Railway PostgreSQL remains the Production-data Source of Truth. Draft PR #363 is research/cutover preparation only; Draft changes do not establish current-main retirement.

## 2. Active/current writer surfaces

### PRE pipeline

Current `run_pre_window_pg.py` invokes:

`collect_candidate_filter_shadow_pg.py`

with `required=False`. Optional failure handling does not make the writer unused; it remains an invoked Production PRE stage.

A natural 2026-09-15 morning Railway run explicitly logged:

- `CANDIDATE_SHADOW_ENABLED=True`
- `CANDIDATE_SHADOW_RULES effective=N02,S01,S02,S03,S04,S05`
- `collect_candidate_filter_shadow_pg.py を実行します。`
- collector `ENABLED=True REQUIRE_COMPLETE_ODDS=True`

Therefore the active PRE chain remains a candidate-shadow writer path.

### `test-beforeinfo-extra`

Railway Production config points at repo `main` with:

`python -u collect_candidate_filter_shadow_pg.py`

This is a no-Cron repository-triggered execution surface, not merely a dormant variable set. Railway deployment `f047dabd-1179-4e87-bc0f-2a0a1e513f80` completed SUCCESS and logged:

- `candidate_rows=11`
- `saved_rows=11`
- S01/S02/S03 matches `1/5/5`

A future matching watched repository change can therefore execute the writer unless this service is separately retired/isolated under an approved Production change.

## 3. Current nightly evaluator/report consumers

Current `run_nightly_results_pg.py` retains multiple consumers of the table:

- stage 2: `evaluate_candidate_filter_shadow_results_pg.py`;
- stage 3: `report_candidate_filter_shadow_performance_pg.py`;
- stage 4: `report_n02_forward_performance_pg.py`;
- stage 13: `report_candidate_filter_shadow_robustness_pg.py`.

The evaluator's `CANDIDATE_SHADOW_EVAL_ENABLED` defaults to `1`, and the nightly wrapper also defaults that value to `1`.

Additional read consumers include N02 robustness, shadow collection health, value/calibration reporting, Bao research/calibration scripts, and other manual/research paths. Archive equivalence or explicit retirement is required where future use must remain possible after old rows leave online PostgreSQL.

## 4. Current V4 same-day dependency

Current `.github/scripts/candidate_discovery_v4_main_feed_pg.py` explicitly reads same-date S01-S05 rows from `v2_candidate_filter_shadow` as **legacy carryover**.

The formal V4 structural core remains separate:

- exactly 6 ranked core races;
- exactly 12 core tickets;
- two core tickets per core race.

The prospective wrapper does not require a minimum legacy-row count. If legacy rows are present, however, they become part of the frozen feed and their deadlines participate in the existing earliest-feed pre-deadline guard.

This distinction matters because the candidate-shadow writer is scheduled independently. On 2026-09-15 the Railway morning service scheduled around 08:15 did not start until about 08:18 and its candidate-shadow stage completed around 08:20, after the GitHub V4 primary's nominal 08:16 checkpoint. Thus same-day legacy presence can vary with independent scheduler timing even when the 6-race/12-ticket V4 core is unchanged.

Frozen interpretation before the 2026-09-16 primary:

- formal V4 evidence is the fail-closed 6-race/12-ticket structural core plus timing/provenance guards;
- S01-S05 legacy carryover is auxiliary/reference data and must be reported separately;
- missing legacy rows must never be reconstructed later using post-outcome information;
- present legacy rows remain subject to the existing full-feed pre-deadline guard;
- retirement of `v2_candidate_filter_shadow` still requires a prospective V4 legacy-carryover removal/replacement contract before zero-consumer can pass.

## 5. Machine-checkable runtime-source contract

Draft #363 now contains a pure/offline inventory contract:

- `research/production_runtime_source_contract.py`
- `tests/test_production_runtime_source_contract.py`
- `.github/workflows/research-production-runtime-source-contract.yml`

Workflow run `35031660983` is SUCCESS. Six synthetic tests enforce fail-closed behavior for missing/duplicate/unresolved service inventory, candidate-shadow writers and destructive inline commands, while explicitly surfacing non-main Railway branches for scanning.

The module has no DB/network/Railway/GitHub/environment access. It is an audit-classification contract only and does not itself prove zero consumers.

## 6. Required retirement ordering

`v2_candidate_filter_shadow` must not be removed or declared zero-consumer until all applicable steps below are completed in this order:

1. preregister and review the future V4 legacy-carryover replacement/removal contract before using subsequent outcomes to justify it;
2. land the approved V4 decoupling and verify current-main no longer requires the table for same-day V4 generation;
3. separately retire/disable the active PRE writer invocation under explicit Production approval;
4. separately retire/isolate the Railway `test-beforeinfo-extra` writer surface under explicit Production approval;
5. retire or archive-adapt the nightly evaluator, performance, robustness and N02 readers;
6. retire or archive-adapt remaining manual/report/research readers as required for reproducibility;
7. take a fresh snapshot of every Railway Production service's actual repo/branch/image/start command, including non-main branches and no-Cron services;
8. rerun current-main direct/indirect code and workflow scans;
9. require `ZERO_CONSUMER=PASS` with no ambiguous/unclassified execution surface;
10. only then proceed to the still-separate permanent-archive, recovery, exact-inventory/digest, fresh retained-set restore/headroom, and destructive-approval gates.

## 7. Explicit non-implications

Archive equivalence for historical candidate-filter analysis does **not** prove current-day V4 independence.

A service having no Cron does **not** prove it cannot execute.

A Draft-only guard or retirement change does **not** count as current-main retirement.

A structurally passing runtime inventory does **not** authorize deletion; archive durability, recovery and Hobby-capacity proof remain separate.

## 8. Current gate

`ACTIVE_PRE_WRITER_PRESENT / TEST_BEFOREINFO_EXTRA_PROVEN_WRITER_SURFACE / NIGHTLY_EVALUATOR_AND_REPORT_READERS_PRESENT / CURRENT_V4_SAME_DAY_LEGACY_CARRYOVER_DEPENDENCY_PRESENT / MACHINE_RUNTIME_INVENTORY_CONTRACT_PASS / ZERO_CONSUMER_BLOCK / NO_DELETE / NO_PRODUCTION_MUTATION / PURCHASE_FALSE`
