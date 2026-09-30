# Historical data source policy — 2026-09-30

Status: APPROVED HISTORICAL ACQUISITION POLICY

## Core timing rule

For historical reconstruction, the value treated as valid for a target race must be a value that is reasonably attributable to information published before the target race deadline.

Priority:
1. exact timestamped pre-deadline value;
2. official pre-race publication whose purpose is the race entry/beforeinfo sheet;
3. strictly prior-day derived value constructed only from already completed official races;
4. otherwise mark as historical reconstruction / timing-assumed and keep separate from prospective evidence.

Historical reconstruction must never be silently relabeled as prospective evidence.

## Source hierarchy

### Tier 1 — BOAT RACE official downloadable files

Primary source for:
- daily program / B files;
- race result / K files;
- racer term statistics.

Use these whenever the official download contains the required field.

B-file entry values are treated as pre-deadline by nature.

K-file results may be used for a target race only when the source race is strictly earlier than the target information cutoff. For generic historical derived features, this project uses prior calendar day unless a stronger timestamp proof is available.

### Tier 2 — BOAT RACE official archived race pages

Use archived racelist and beforeinfo pages for fields not fully available in B/K files.

Current contracts include:
- archived racelist values treated as historical pre-deadline entry-sheet reconstruction;
- archived beforeinfo values treated as historical pre-deadline exhibition/weather reconstruction.

All writes:
- fill missing only;
- preserve existing non-null data;
- carry a historical source label;
- do not become prospective evidence.

### Tier 3 — prior-only derived historical features

Allowed when chronology is structurally enforced.

Examples:
- Course applied-term proxy built only from a completed prior aggregation term;
- Opponent replay using only dates strictly before target date;
- recent_form built only from prior calendar-day official K results.

Derived fields must record:
- source contract;
- historical_reconstruction=true;
- prospective_evidence=false.

### Tier 4 — 艇国データバンク supplemental source

艇国データバンク is useful for:
- cross-checking historical schedules/results;
- motor/boat history and aggregate periods;
- residual fields that cannot be recovered adequately from official sources.

Rules:
- obey the site's program/tool access policy;
- at least 3 seconds between automated requests;
- use known valid URLs only;
- do not use multiple IPs to accelerate collection;
- for program tables, race results and racer term statistics, prefer BOAT RACE official downloads as the site itself requests;
- do not copy bulk site content when the official source already provides the same data.

Current infrastructure note:
- public web access to 艇国DB is confirmed;
- Railway direct HTTPS access to the tested motor page timed out repeatedly;
- therefore 艇国DB is currently a supplemental/manual-verification source, not the high-volume Railway backfill path;
- bulk automation should be activated only after a stable compliant network path is validated.

## Current approved historical acquisition set

Starting 2025-07-01:
- official B entry backfill;
- archived racelist residual entry backfill;
- prior-only Opponent replay;
- official archived beforeinfo exhibition/weather backfill;
- applied-term Course proxy;
- prior-day-only recent_form reconstruction.

Historical data may improve matched-contract backtests, but no historical reconstruction alone authorizes Production promotion.

## Model scope

The 2026-10-15 V5 core scope lock remains unchanged.

Historical acquisition can continue aggressively in parallel without forcing newly acquired fields into V5 core.

`OFFICIAL_FIRST / PREDEADLINE_OR_PRIOR_ONLY / HISTORICAL_LABEL_REQUIRED / TEIKOKU_SUPPLEMENTAL / NO_SILENT_PROSPECTIVE_RECLASSIFICATION`
