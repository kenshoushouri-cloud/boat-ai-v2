# V4 capture resilience preregistration

Status: `RESEARCH_ONLY / FUTURE_DATES_ONLY / NO_BACKFILL / NO_PRODUCTION_MUTATION`

Date frozen: 2026-09-15 JST

## Incident that motivates this plan

The first scheduled formal Candidate Discovery V4 prospective freeze was expected at **08:16 JST** on 2026-09-15 from default branch `main`.

The workflow file was present on `main`, had the intended `16 23 * * *` cron, read-only PostgreSQL guard, `purchase_action=false`, pre-deadline checks, and immutable artifact hashing.

The scheduled event eventually appeared as GitHub Actions run **`34917166205`**, but not until **10:25 JST**:

- event: `schedule`
- main SHA: `61f7d6e75629ffb549a583f00bfd5dd58c186a71`
- scheduled target resolved correctly to `2026-09-15`
- freeze started: `2026-09-15T10:25:18.860949+09:00`
- freeze completed its candidate-feed computation at approximately `10:25:20 JST`
- earliest frozen-feed deadline: `2026-09-15T09:36:00+09:00`
- scheduler delay relative to the planned 08:16 start: approximately **2 h 9 min**

The inner read-only candidate feed produced 6 core races / 12 core tickets and read no result or payout rows, but the prospective wrapper correctly rejected the run because it was already after the earliest frozen-feed deadline:

`RuntimeError: prospective freeze was not completed before earliest frozen-feed deadline`

The immutable prospective artifact upload step was skipped. The late-generated candidate list is diagnostic only and must never be scored as formal prospective evidence.

Therefore 2026-09-15 formal V4 prospective evidence is permanently classified:

`UNAVAILABLE / LATE_SCHEDULED_CAPTURE_REJECTED_PREDEADLINE_GUARD`

This supersedes the earlier provisional classification `MISSING_SCHEDULED_CAPTURE`. It must never be regenerated, backfilled, or relabeled as prospective after the fact.

## Goal

Prevent scheduler delay or scheduler miss from silently losing another full Forward day without weakening the evidence contract.

This plan applies only to future dates after it is explicitly adopted. It does not authorize a Production model, DB, Railway, LINE, purchase, threshold, or staking change.

## Invariants

Any primary or fallback capture must retain all current V4 safety requirements:

- target date equals current JST date;
- source cutoff is 08:15 JST;
- generation starts only after the source cutoff;
- scheduled/evaluable universe is complete;
- exactly 6 core races / 12 core tickets;
- every frozen row is generated before the earliest relevant race deadline;
- no result/payout table may be read;
- `prospective_evidence_eligible=true`;
- `purchase_action=false`;
- `promotion_allowed=false`;
- DB session remains read-only;
- immutable artifact + SHA-256;
- no result-after reconstruction.

## Proposed resilient capture contract

### Primary channel

Keep the existing GitHub scheduled capture at 08:16 JST.

The 2026-09-15 incident proves that GitHub scheduled execution can be delayed far beyond the safe evidence window. The primary therefore must not be the only capture channel.

### Independent fallback channel

Use a second scheduler that is operationally independent of the primary GitHub scheduled event. Candidate implementations, in preferred order for review:

1. a small read-only Railway Cron dedicated to V4 evidence capture;
2. a pre-registered exact-time orchestration task that dispatches the existing GitHub `workflow_dispatch` only when the primary run is missing;
3. a second GitHub schedule only as a weaker fallback because it shares the same scheduler failure domain.

The preregistered fallback checkpoint is **08:25 JST exactly**. Scheduler delivery may itself be late, but the intended checkpoint must not be moved later based on same-day observations. The actual run remains valid only if all original timing guards pass. The 08:25 checkpoint provided substantial headroom before the observed 09:36 earliest frozen-feed deadline on the 2026-09-15 incident date; that incident-specific margin must **not** be generalized into a claim that 08:25 is always safely early. The checkpoint is an operational resilience checkpoint, not a model threshold or an evidence-validity override.

At the fallback checkpoint, the fallback should no-op when a valid primary artifact for the same target date is already independently observable. Otherwise it may attempt capture only while all original prospective guards can still pass. If timing is no longer safely pre-deadline, it must fail closed and mark that date unavailable.

No fallback may use results, payouts, post-race data, or a reconstructed candidate set.

### Timing-feasibility clarification frozen before the 2026-09-16 primary

A natural 2026-09-16 data-preparation run completed before the primary and populated a full 156-race / 936-entry universe with no failed race task. The earliest prepared race deadline observed in that universe was **08:32 JST** (`20260916_14_01`). Therefore an 08:25 checkpoint can have as little as **7 minutes of worst-case wall-clock margin** if such an early race becomes part of the frozen feed.

This observation was recorded before the 2026-09-16 08:16 primary and before outcomes. It does not retune the 08:25 checkpoint and does not activate fallback. It clarifies the adoption rule:

- 08:25 is a fixed attempt checkpoint, not a guarantee of sufficient per-date headroom;
- formal validity is determined only by the existing actual-start/actual-completion versus earliest-frozen-feed-deadline guard;
- a fallback delivered late, or one whose generated feed includes a deadline too close to completion, must fail closed even if it was nominally scheduled for 08:25;
- no same-day deadline observation may be used to move the checkpoint later or rescue an otherwise invalid capture;
- before Production activation, fallback operational testing must demonstrate that the chosen independent scheduler and capture runtime are plausibly capable of completing within the available prospective window, while preserving the original fail-closed guard as final authority.

The prepared-universe earliest deadline is not itself the formal frozen-feed deadline. The actual feed may or may not contain that race. It is used here only to reject the unsafe assumption that every date resembles the 2026-09-15 09:36 incident margin.

## Daily official-artifact rule

For any future date with more than one valid pre-result capture, define the official V4 Forward evidence prospectively as:

1. every candidate artifact must independently satisfy the full safety contract;
2. choose the unique valid artifact with the earliest `generated_at_jst` after 08:15 JST;
3. if multiple artifacts have the same earliest `generated_at_jst` and the same **canonical formal-core payload SHA-256**, treat them as duplicate copies of the same formal core evidence and retain one deterministic metadata record for audit;
4. if multiple artifacts have the same earliest `generated_at_jst` but different canonical formal-core SHA-256 values, do **not** choose by GitHub/Railway run ID or channel identity; classify the date `UNAVAILABLE / AMBIGUOUS_DUPLICATE_CAPTURE` and preserve both artifacts as diagnostic evidence only.

GitHub and Railway run identifiers are provider-local identifiers and must not be compared numerically to decide evidence precedence.

Any later valid capture is diagnostic-only and must not be mixed into formal Forward scoring.

If the primary succeeds, fallback should no-op where technically possible. If duplicate execution still occurs, the earliest-valid rule removes ordinary ambiguity without changing predictions after outcomes, while formal-core disagreement at the same earliest timestamp remains fail-closed.

The full artifact SHA-256 and canonical formal-core SHA-256 serve different purposes and must both be retained:

- **full-file SHA-256** proves byte integrity of the exact artifact, including timestamps/provenance and any auxiliary legacy content;
- **canonical formal-core SHA-256** proves equality of the frozen structural 6-race/12-ticket evidence across channels while excluding capture-channel/timestamp noise and auxiliary legacy carryover.

## Pure artifact-arbitration and canonical-core contract

Before the 2026-09-16 primary and before outcomes, Draft PR #364 added:

- `research/candidate_discovery_v4_capture_arbiter.py`;
- `tests/test_candidate_discovery_v4_capture_arbiter.py`;
- `.github/workflows/candidate-discovery-v4-capture-arbiter.yml`.

Latest focused run **`35033821144`** passed **11/11 synthetic tests** plus pure/offline isolation. The tests cover:

- unique-earliest valid capture selection;
- same-time/same-hash duplicate collapse;
- same-time/different-hash fail-closed behavior;
- provider-run-ID non-precedence;
- invalid capture rejection;
- cutoff/core completeness;
- purchase/promotion/pre-deadline safety flags;
- canonical hash stability across capture timestamp/provenance changes;
- canonical hash stability when only auxiliary legacy rows/annotations change;
- canonical hash change when a formal core ticket changes;
- canonical hash change when frozen formal policy or structural score changes;
- fail-closed behavior for incomplete/invalid core ticket ordering.

The canonical payload includes the structural universe diagnostics, frozen formal policy, six ranked core races, relevant structural fields/deadlines and only `core_order` 1-2 tickets. It excludes provider/run metadata, capture/freeze timestamps, file hashes, legacy-only races/tickets and LEGACY annotations on otherwise identical core tickets.

The arbiter and canonicalizer do not run a capture, access Production data or providers, write files, send LINE, or authorize purchase/promotion.

Draft #364 also wires the future prospective-freeze workflow to emit both the normal full-file `.sha256` and `candidate-discovery-v4-prospective-freeze.json.core.sha256`. On PR validation, workflow run **`35033919799`** completed the safety job successfully and correctly skipped the actual freeze job. This wiring is **Draft only**; current `main` does not emit the canonical-core hash unless an approved future merge lands it.

Passing these tests closes the canonical-hash definition and duplicate-selection contract portions only. Primary-vs-fallback operational equivalence under an actually selected independent fallback execution path remains an open adoption gate.

## Legacy carryover provenance clarification frozen before the 2026-09-16 primary

A pre-primary static audit found that current `main` selects the formal six-race core before appending S01-S05 rows from `v2_candidate_filter_shadow`, and `summary.core_tickets` counts only tickets with a non-null `core_order`. Therefore candidate-shadow legacy carryover does **not** determine or rerank the formal structural 6-race/12-ticket core.

However, the current legacy query is scoped by target `race_date` and rule ID and ordered by `snapshot_at`, but it does **not** enforce `snapshot_at < 08:15 JST`. Course and Opponent Pressure inputs do enforce the frozen cutoff.

This was discovered and recorded before the 2026-09-16 primary and before outcomes. The preregistered interpretation is:

- the 6-race/12-ticket structural core remains the formal V4 evidence unit;
- legacy carryover is auxiliary/reference evidence and is excluded from canonical formal-core equivalence;
- no missing legacy row may ever be reconstructed after the fact;
- any legacy row present in the full artifact still remains subject to the existing full-feed pre-deadline guard;
- before fallback adoption or candidate-shadow retirement, legacy auxiliary evidence must either remain outside formal canonical equivalence or gain an explicit pre-08:15 provenance guard with unknown/late timestamps failing closed.

This clarification does not modify `main`, candidate selection, or Production behavior.

## Capture bootstrap failures are evidence failures

A static check of the current `main` scheduled workflow before the 2026-09-16 primary confirms that the formal freeze job performs environment/bootstrap work before the guarded Python freeze itself: Python setup, Node setup, `pip install -r requirements.txt`, global Railway CLI installation, target-date resolution, and read-only database-URL resolution. A transient failure in any of those steps can prevent a formal artifact even when the scheduler fires on time.

This is part of the evidence contract, not a reason to weaken it:

- if the scheduled primary fails before producing a valid guarded artifact, that channel did **not** produce formal Forward evidence;
- classify such a day/channel as `UNAVAILABLE / CAPTURE_BOOTSTRAP_FAILURE` (or a more specific preregistered infrastructure reason) unless an independently preregistered fallback already produces a valid artifact under the full original guard;
- do not manually rerun or dispatch the primary after observing the failure and then relabel the later artifact as the missing scheduled evidence;
- a later diagnostic run may help root-cause infrastructure, but it is not the original formal capture;
- dependency-install success, credential resolution, and provider availability must never relax the source cutoff, complete-universe, pre-deadline, no-result-read, or purchase/promotion false requirements.

This clarification was frozen before the 2026-09-16 08:16 primary and before outcomes. It does not activate a fallback and does not modify the `main` workflow.

## Monitoring requirement

A daily read-only audit should record:

- target date;
- primary run present/missing/late;
- primary scheduled-vs-start delay;
- bootstrap/setup stage reached and any failure stage;
- fallback checkpoint and actual start time;
- fallback invoked/not invoked;
- capture channel;
- provider-local run ID / head SHA;
- generated_at_jst;
- earliest relevant deadline;
- 6-race / 12-ticket completeness;
- artifact ID/name;
- canonical formal-core SHA-256 and full-file/archive SHA-256 where applicable;
- `prospective_evidence_eligible`;
- `purchase_action`;
- final classification: `FORMAL_AVAILABLE` or a specific `UNAVAILABLE / ...` reason.

A missing, bootstrap-failed, or late-rejected day is acceptable evidence. A reconstructed day is not.

## Adoption gate

Before any fallback scheduler is activated:

- choose exactly one independent fallback mechanism;
- freeze its 08:25 JST checkpoint and permission boundary before the first date it can affect;
- prove it cannot write Production DB or send LINE/purchase actions;
- prove operational timing feasibility without weakening the actual pre-deadline fail-closed guard;
- make every channel emit/record the same frozen canonical formal-core hash contract plus its exact full-file hash;
- prove primary/fallback formal-core equivalence under identical frozen source inputs;
- retain duplicate-artifact selection and fail-closed payload-disagreement tests;
- resolve legacy auxiliary provenance as described above;
- preregister the official-artifact rule on `main` before the next date it is used;
- obtain any explicit Railway Production approval if a Railway Cron/service is selected.

Current decision:

`2026-09-15_UNAVAILABLE_LATE_GITHUB_SCHEDULE / FAIL_CLOSED_WORKED / FUTURE_CAPTURE_RESILIENCE_PREREGISTERED / FALLBACK_CHECKPOINT_0825_FIXED_BUT_NOT_UNIVERSALLY_SAFE / TIMING_FEASIBILITY_GATE_ADDED / CAPTURE_BOOTSTRAP_FAILURE_FAIL_CLOSED / CANONICAL_FORMAL_CORE_HASH_DEFINED / CAPTURE_ARBITER_11_OF_11_PASS / DRAFT_FUTURE_WORKFLOW_DUAL_HASH_SUCCESS / LEGACY_AUXILIARY_EXCLUDED_FROM_FORMAL_CORE_EQUIVALENCE / CROSS_PROVIDER_RUN_ID_TIEBREAK_REJECTED / AMBIGUOUS_DUPLICATE_FAIL_CLOSED / NO_BACKFILL / NO_FALLBACK_ACTIVATED_YET / PURCHASE_FALSE`
