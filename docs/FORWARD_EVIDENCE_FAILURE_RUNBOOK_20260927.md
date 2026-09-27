# Forward Evidence Failure Runbook — 2026-09-27

Purpose: fail closed consistently without reconstructing evidence or converting missing/invalid races into losses.

## 1. Primary prospective-freeze delayed or failed

Check:
- workflow event / start time;
- whether a valid immutable formal artifact exists;
- artifact eligibility / pre-deadline provenance.

If no valid primary artifact is observable at fallback checkpoint:
- independent fallback may dispatch according to its frozen arbiter;
- do not manually reconstruct the day's formal core from later DB state.

If a valid primary artifact exists:
- do not create a second formal evidence decision.

## 2. Fallback also fails or misses deadline

Classification:
`UNAVAILABLE_NO_VALID_CAPTURE`.

Action:
- preserve the date as unavailable;
- do not backfill from historical/current DB state;
- do not insert synthetic formal evidence;
- do not use the date in FORMAL_AVAILABLE rolling lookbacks.

The unavailable date is missing evidence, not a losing bet.

## 3. Formal artifact exists but result DB is not ready

Action:
- classify as pending;
- investment = 0 until official settlement exists;
- rerun settlement later against the same immutable artifact.

Forbidden:
- treat pending as miss;
- replace the formal artifact;
- regenerate tickets after outcomes.

## 4. Race is cancelled / invalid / non-official

For Candidate Filter rows:
- `evaluation_status=invalid_result`.

For immutable formal settlement:
- `official=false`.

Economic semantics:
- investment = 0;
- return = 0;
- excluded from ROI denominator;
- excluded from losing streak / drawdown sequence;
- retained in coverage/void counts.

Do not charge a 100 JPY loss.

Common definition source:
- Draft #415 common Forward economics;
- parity evidence: Draft #416.

## 5. Candidate-shadow result is official

Only `evaluation_status=evaluated` is economically settled.

Include:
- investment;
- hit/miss;
- return;
- ROI;
- drawdown;
- losing streak;
- bootstrap.

Pending/unknown rows do not enter economic denominator.

## 6. V4 formal artifact hash / shape validation fails

Fail the evidence item.

Do not:
- repair the artifact from DB;
- substitute another artifact selected after seeing results;
- weaken exact 6R / 12-ticket requirements;
- change canonical-core hash.

Provider inventory/arbitration must choose the formal artifact before result access.

## 7. Day-strength shadow cannot classify

If target formal artifact is unavailable:
- no KEEP/SKIP label.

If fewer than seven prior FORMAL_AVAILABLE days exist:
- `NOT_READY`.

If classification exists:
- it remains shadow-only;
- formal TOP6/TOP2 action is unchanged.

For 2026-09-28:
- frozen prior-seven reference: `0.93817204`.

## 8. S03_M2 Forward row timing fails

Require:
- stored `snapshot_at < deadline_at`;
- exact frozen rule;
- official `evaluation_status=evaluated` for economics.

Any timing-invalid row:
- exclude from prospective economic evidence;
- do not reconstruct an earlier snapshot.

Historical pre-freeze S03 profitability remains rejected as promotion support.

## 9. F-count companion fails

Formal V4 must remain valid and unchanged.

Fail closed:
- no companion artifact for that target day;
- no partial companion;
- no formal rewrite;
- no selector/TOP6/TOP2 change;
- no LINE/BUY.

Actual F-count live capture is not active unless separately approved.

## 10. Railway fallback service config differs unexpectedly

Before any future approved Cron change, re-read service config.

Only approved candidate delta may be:
- `cronSchedule: 25 23 * * * -> 20 23 * * *`.

If any other source/build/start-command/runtime/replica field changes:
- stop;
- do not proceed as a timing-only change.

Current Production remains 08:25 JST until separately approved.

## 11. Evidence review order

When a discrepancy appears:
1. immutable artifact / stored source provenance;
2. settlement status;
3. common economic semantics;
4. track-specific rule;
5. docs/handoff.

Never resolve a discrepancy by tuning a candidate threshold from outcomes.

## 12. Current source registry

Use:
- `docs/RESEARCH_PR_REGISTRY_20260927.md`

Current decision sources:
- #409 formal V4 economics;
- #405 S03_M2 prospective Forward;
- #411 future-only day-strength shadow;
- #415/#416 common economic semantics/parity.

Operational/F-count preparation:
- #412 fallback timing;
- #397/#398/#400/#413 F-count chain.

`FAIL_CLOSED / NO_RECONSTRUCTION / INVALID_RESULT_VOID / PENDING_NOT_LOSS / FORMAL_ARTIFACT_IMMUTABLE / PURCHASE_FALSE`
