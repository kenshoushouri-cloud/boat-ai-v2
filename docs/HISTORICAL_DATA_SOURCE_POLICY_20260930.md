# Historical data acquisition policy — 2026-09-30

Status: `USER_APPROVED / ACTIVE_RESEARCH_ACQUISITION / PROD_MODEL_UNCHANGED`

## User-approved rule

Historical missing data should be acquired aggressively.

For historical reconstruction, a value may be treated as admissible model input when:
1. the field is, by definition, information that exists before that race's deadline; and
2. the source can identify the target race/date/racer sufficiently; and
3. the parser excludes result/payout/outcome sections; and
4. provenance is retained.

This is a deliberate project rule for historical reconstruction. It does **not** make a reconstructed row identical to a prospectively timestamped row. Reports must keep those evidence classes separate.

## Evidence classes

### A — prospective timestamp-clean
Captured before the race deadline at the time.

Use: strongest Forward/promotion evidence.

### B — historical reconstructed predeadline-assumption
Fetched later, but the field itself belongs to the pre-race information set by construction.

Examples:
- official B/program values;
- historical race-card class / national / local / average ST / motor / boat fields;
- race-card F/L count;
- pre-race deadline;
- event progress visible in the race card;
- other explicitly preregistered pre-race fields.

Use: historical matched-contract/backtest and data-coverage repair.
Must be labeled reconstructed, never silently relabeled prospective.

### C — outcome-only
Examples:
- official K/result archive;
- finish order;
- winning ticket;
- payout;
- final result/status.

Use: settlement/labels only. Never feature input.

### D — inadmissible for historical feature reconstruction
Examples:
- a current rolling aggregate whose aggregation window includes races after the target race;
- post-race edited/derived values when the pre-race value cannot be isolated;
- any field whose timing role is unknown.

Use: none until timing is proven.

## Source precedence

1. **BOAT RACE official downloads / official historical race pages**
2. **艇国データバンク for fields not adequately available from official downloads**
3. Other sources only after a separate source/timing review

BOAT RACE official provides racer term files, program downloads, and result downloads. Program and term data should be acquired from official first.

艇国DB explicitly asks program tables, race results, and racer term records to be obtained from BOAT RACE official. We therefore do not duplicate those categories from 艇国 when official data is available.

## 艇国DB automation constraints

Enforced:
- at least 3 seconds between requests;
- one sequential process;
- no IP rotation;
- no CSS/JS/image/favicon fetches;
- only known existing historical race-detail URLs;
- no brute-force nonexistent URLs.

For historical race-detail pages, raw HTML is saved first with:
- target date;
- venue;
- race number;
- source URL;
- fetch timestamp;
- SHA256.

A later audited parser may read only the preregistered pre-race section.

## Immediate acquisition plan

### Phase 1 — official raw bulk
Acquire 2025-07-01 onward:
- B program LZH -> historical input source
- K result LZH -> settlement source only
- SHA256 manifest for every fetched file

### Phase 2 — official parse
Parse B into race/racer historical predeadline fields with explicit source class B.
Parse K only into settlement labels.

### Phase 3 — 艇国 gap fill
After comparing official B coverage against required V4/V5/V5.1 fields, query only the missing fields/races from 艇国, sequentially at >=3 seconds/request.

### Phase 4 — matched-contract backtest
Build datasets that can distinguish:
- prospective timestamp-clean rows;
- historical reconstructed predeadline-assumption rows;
- missing rows.

No result-derived feature is permitted.

## Production invariants

Unchanged:
- Production V4 model/selector/threshold/TOP6/TOP2/stake;
- LINE logic;
- automatic purchase disabled;
- `purchase_action=false`.

`HISTORICAL_BACKFILL_APPROVED / PREDEADLINE_FIELD_SEMANTICS_ACCEPTED / PROSPECTIVE_CLASS_STILL_SEPARATE / OFFICIAL_FIRST / TEIKOKU_GAP_FILL_RULES_ENFORCED / NO_MODEL_CHANGE / PURCHASE_FALSE`
