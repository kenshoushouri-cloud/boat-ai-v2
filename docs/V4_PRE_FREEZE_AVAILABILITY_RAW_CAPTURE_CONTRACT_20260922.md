# Candidate Discovery V4 pre-freeze official availability raw capture contract — 2026-09-22

Status: `RESEARCH_ONLY / PRE_FREEZE_RAW_CAPTURE / NO_PRODUCTION_WIRING / NO_RESULT_OR_PAYOUT_READ / PURCHASE_FALSE`

## Problem closed by this contract

The availability guard requires every evidence observation to be at or before the V4 artifact freeze timestamp.

Therefore the following sequence is invalid for formal PASS:

`freeze six races -> fetch official availability -> call that pre-freeze evidence`

Even if the fetch occurs before every selected race deadline, it happened after the formal freeze and cannot prove what was observable when the core was frozen.

The safe order is:

`08:15 source cutoff -> capture official availability raw for the same-day venue universe -> freeze V4 core -> bind selected core races to preserved raw rows`

No after-result page is used to reconstruct this evidence.

## Capture universe

The preferred research capture request is derived mechanically from the full same-day scheduled/evaluable race universe. The universe builder validates every `race_id / venue_id / race_no / deadline_at`, sorts the normalized rows, and computes a deterministic `race_universe_sha256`.

The resulting request carries:

- exact target date;
- unique official venue IDs `01..24`;
- exact scheduled-race count;
- deterministic race-universe SHA-256;
- a hard stop equal to the **earliest scheduled race deadline in that universe**.

This prevents a future caller from silently choosing a later hard stop based only on the six selected core races.

The capture plan is deterministic and contains only:

1. one same-day official index:
   `https://www.boatrace.jp/owpc/pc/race/index?hd=YYYYMMDD`
2. one official race-index page for every scheduled venue:
   `https://www.boatrace.jp/owpc/pc/race/raceindex?hd=YYYYMMDD&jcd=XX`

Result and payout endpoints are not caller-configurable and are not part of the plan.

## Timing gates

The capture fails closed unless:

- execution is on the target date in JST;
- capture starts at or after 08:15 JST;
- capture starts before the preregistered earliest scheduled deadline;
- every source finishes before that hard stop;
- the final capture completes before that hard stop.

A later V4 freeze must still independently verify that each evidence `observed_at` is at or before the artifact freeze timestamp.

## Preserved evidence

The raw manifest also repeats the scheduled-race count and race-universe SHA-256 so the preserved official sources remain tied to the exact pre-freeze universe identity.

For every source the raw manifest records:

- exact canonical requested/final URL;
- exact raw bytes in a separate file;
- byte count;
- observation time;
- SHA-256 of the exact raw bytes.

Unexpected redirects, empty payloads, oversized payloads or timing overrun fail closed.

## One venue source, multiple selected races

A venue `raceindex` page contains multiple race rows. Re-fetching the same page once per selected race is unnecessary and can create avoidable timing drift.

The active parser now hashes the exact bound race-row excerpt as `evidence_binding_sha256`.

The guard may reuse one pre-freeze source for multiple active selected races **only when**:

- all uses are at the same venue;
- every use is race-scoped `active`;
- every selected race carries a valid lowercase 64-hex row-binding SHA;
- those row-binding SHAs are distinct.

Whole-venue/range unavailable reuse rules remain unchanged.

## Current limitation

This Draft defines and tests the capture contract but does not wire it into the current main prospective-freeze workflow.

A Production-effect merge/wiring would require explicit approval. Until then, current V4 formal days continue under the existing contract; post-result pages must not be used to manufacture missing pre-freeze availability evidence.

## Safety

`PRE_FREEZE_ONLY / EXACT_RAW_BYTES / SHA256_BOUND / NO_RESULT_READ / NO_PAYOUT_READ / NO_DB_WRITE / NO_RAILWAY_CHANGE / NO_LINE / PURCHASE_FALSE`
