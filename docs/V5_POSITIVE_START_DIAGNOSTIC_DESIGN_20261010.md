# V5 — Positive Six-Active Official Source Discovery (design only)

Date: 2026-10-10 JST. Status: **DESIGN REVIEW ONLY / NO LIVE RUN APPROVED**.
Owner: V5 mainline; V4 Production is protected.

## 1. Problem / current evidence
- The completed 2026-10-10 Edogawa 1R read-only racelist + beforeinfo probe examined anonymized header counts and 6/6 exhibition completeness. Neither constitutes an official affirmative **six active starters** status. **Do not rerun it**.
- Existing `v5/official_start_status_observation_pilot.py` accepts 1–2 race IDs, GETs racelist and beforeinfo once each, 12-second request timeout, exact URL checking and no retries. `v5/official_http_transport.py` captures raw bytes in memory and completion time but does **not** prove earliest observation or publish time.
- `v5/official_positive_start_evidence_contract.py` deliberately has `APPROVED_POSITIVE_SOURCE_SCHEMAS = frozenset()`, and always refuses prewrite and Forward. Keep it unchanged.
- **Question:** Does a **documented, authoritative official source field** affirmatively state that all six **specific lane–racer pairs are active** before the decision deadline? Listing six entrants, exhibition attendance, open betting, implied odds, the words `出走` or `確定` in generic headings, and the absence of a `欠場/取消` notice are NOT affirmative proof.

## 2. Scope / absolute prohibitions
- This document authorizes **ZERO network requests**. Any future live attempt requires a separately reviewed plan and explicit, race-specific user approval. No scheduled job, background retry, auto-selection, CI live access, or autonomous Railway operation.
- Proposed **new** live diagnostic, if independently authorized: **one distinct currently scheduled race**, **at most 2 total official HTTPS GET attempts** inclusive of errors, no redirect and no retry, strictly within the real **8–15 minutes before the verified official deadline**. Never target the already completed Edogawa `20261010_03_01` probe.
- No production DB/DDL, service deploy, volume resize/delete, collector, V4 selector, LINE, stake, purchase/BUY, or V5 active routing. No full source HTML, raw racer registration IDs, names, credential strings or race page body in durable reports/logs; raw bytes may be held transiently in memory and discarded.
- Use an **exact URL allowlist** of pre-reviewed official host + path + query keys for the selected source, not arbitrary user-controlled URLs. Candidate URL/schema must be identified in advance using official published information; if not verifiable, **abort with zero GETs**.

## 3. Preflight (OFF by default; any failure => zero GETs)
1. Record review ticket identifying ONE untested race (JST YYYYMMDD/venue/R), source schema provenance (official publisher, published specification or directly independently reviewable official field semantics), and manual approval for exactly this race and these URLs. A header-search keyword or inference is insufficient provenance.
2. Independently check/record actual official closing time, race day, timezone, and V5 decision cutoff. Explicitly reject races already passed or with uncertain official deadline. Enforce `official_deadline - 15min <= observation_start <= official_deadline - 8min`; recheck before **each** GET and stop if the deadline/cutoff condition no longer holds. Preserve a conservative local clock-quality caveat.
3. Freeze allowed origin/endpoint: ideally GET #1 the official source page containing the *candidate affirmative field* (NOT just six listed entrants); only if needed GET #2 an independent official racelist to bind 6 unique registered racers to boats 1–6. If the first source has no authoritative candidate, do not spend a second GET merely searching arbitrary pages.
4. Use an injected, explicit HTTP session and runtime opt-in separate from any `first_write_confirmed`, `active` or other caller-supplied boolean. Must reject automatic CI/prod invocation. Keep all Network/DB side effects absent on module import.

## 4. Proposed acquisition and evidence review (NOT implemented in this task)
- Exactly fixed HTTPS URL, status 200, no redirects, fail closed on content-length/body limit, malformed content, URL mismatch, parse error, identity ambiguity, clock mismatch or cutoff breach. No retries, even on HTTP failure.
- Count attempted requests **before** each GET, cap 2 and terminate early. Current transport's 12-second timeout is a per-request timeout, **not a proven 24-second total wall-clock bound**; a future implementation must add an independent overall deadline/cancellation strategy if a hard duration cap is needed.
- For each response, record in-memory SHA-256, bounded byte size, request start + response-body completion times (JST + explicit UTC offset), exact source classification; do not equate completion with first published or first-ever fetched timestamp. Do not store original response bytes or identity-bearing extracts in the diagnostic report.
- Validate candidate field **per lane 1..6**, including distinct official racer registration values (temporarily parsed in memory only), race ID, effective/as-of semantics, and affirmative status vocabulary defined by its **official source schema**. An unrecognized/missing field, duplicate lane/racer, a negative-only scratch list, or six exhibition numbers yields **NO_PROOF**.
- A positive-looking field in one network sample is at most `CANDIDATE_FIELD_SEEN_UNVERIFIED`. Neither it nor a caller-provided `approved` boolean automatically changes `APPROVED_POSITIVE_SOURCE_SCHEMAS`, `six_active_starts_confirmed`, `beforeinfo_first_write_eligible` or `forward_eligible`: all remain FALSE.
- Persist at most an anonymous scope report: race ID, approved URL *type* / path key (no arbitrary query contents), attempted GET count <=2, official deadline/cutoff, UTC/JST timestamps, byte sizes/digests, parser version, six-lane **count and boolean consistency** (never identities), evidence reason code, and `forward_eligible=false`. No page text snippets, names or full URLs with unvetted parameters.
- Diagnostic output reason codes: `NOT_APPROVED`, `NO_AUTHORITATIVE_SCHEMA`, `OUTSIDE_PREDEADLINE_WINDOW`, `OFFICIAL_DEADLINE_UNVERIFIED`, `HTTP_UNVERIFIED`, `NON_AFFIRMATIVE_SOURCE`, `SIX_LANE_BINDING_UNVERIFIED`, `CANDIDATE_FIELD_SEEN_UNVERIFIED`. All outcomes HOLD.

## 5. No-live validation checklist (future separate task)
- Inject fake session + frozen JST clock only. Validate: opt-in absent => zero GET; source schema missing => zero GET; race/date/deadline mismatch => zero GET; window earlier/later than 8–15 minutes => zero GET; same Edogawa probe => zero GET; fake redirect/error => no retry; malformed/oversize => no PII leak.
- Six exhibition records or absence of `欠場` must fail; six distinct entrants without six independently affirmative statuses must fail; duplicated lane/racer, conflicting authoritative field, or stale response must fail. Even six positive sample fields return **UNVERIFIED** pending independent source and immutability review.
- Assert no changes to V4, Railway DB, LINE, stakes, BUY, collector or Forward. Tests must NEVER touch real official websites.

## 6. Promotion gate (separate later work, not this diagnostic)
Require all: officially documented/reviewed positive per-lane schema, authentic original bytes audit, six unique source-bound racers, verified *actual* first-observed immutable write, independent DB owner/readback and unaltered provenance, and strict predecision timestamps. Only after independent review can a separate proposal modify approval registry / prewrite/Forward HOLD. Then perform same-eligible-race V4/V5 Forward and 3連単 net ROI; **do not activate BUY now**.

Decision: **No confirmed official positive six-active source schema today; V5 beforeinfo first-write and Forward remain safely blocked.**
