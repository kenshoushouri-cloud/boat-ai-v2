# V5 official postrace HTML fixture: 1-request acquisition review (2026-10-10 JST)

**Status: PREPARED / NOT EXECUTED / requires explicit race-specific user approval.** No GET, CI, Railway, database, production or wager occurred. This is for **V5-only** settlement/parser verification; V4-vs-V5 comparison is not required.

## Read-only repository evidence (verified on current main)
- Queried complete default-branch recursive tree: **1,046 items / 1,026 blobs, `truncated=false`**.
- Only **8** .html/.htm/.mhtml/.warc/.json/.jsonl/.ndjson/.gz/.zip/.lzh/.txt candidate data files were present, and **zero saved .html/.htm/.mhtml or archived original race-result HTML fixture**. The existing `tests/test_v5_offline_trifecta_refund_section.py` synthesizes HTML in Python; it is not official bytes.
- `result_detail_pg.py` obtains F/L finish/start statuses but not an authenticated explicit refund subsection. `repair_month_all_pg.py:parse_result` parses printed 3連単 ticket/payout from page text and does not identify refundable ticket sets. Offline new parser `v5/offline_trifecta_refund_section.py` assumes an exact isolated `返還` → `決まり手` section and must be validated against *real markup*, not made permissive without evidence.
- File-tree inspection does not audit Railway database contents or historical files outside GitHub. No claim that no source exists anywhere; only **no repository fixture located**.

## Proposed ONE public official archived result (candidate, not fetched this turn)
- **Race identity:** 2025-01-23, venue `08`, race `9R`; archival result identity `20250123_08_09`.
- Official expected endpoint, built using the existing repo's `_official_url('raceresult', ...)` URL format:
  `https://www.boatrace.jp/owpc/pc/race/raceresult?rno=9&jcd=08&hd=20250123`
- This was previously cited as an *indexed* F/返還 example in compact handoff. Actual current response body, layout, availability and official refund state are **NOT verified**. This 2025 archival page could only serve as a **postrace parser fixture**; retrieving it in October 2026 CANNOT prove the race's 2025 predeadline odds were actually available as-of.
- Do not fetch any extra race, odds, beforeinfo or historical page in this step.

## Preconditions before a later one-off GET
1. User explicitly authorizes **exactly this archived race URL**, 1 request, no retries; previous generic requests to continue implementation do not count as approval to alter the existing diagnostic rule.
2. Strict HTTPS and exact host/path/query allowlist; **1 attempt maximum**, GET via a non-production isolated client; redirect disabled, timeout ≤12 seconds, byte cap ≤2 MiB, stop on any HTTP/encoding/content mismatch. Keep raw response intact in a private temporary local file only if an accessible permitted container can do so safely (no repo committed full personal pages or Railway volume). Otherwise retain in-memory transient bytes and report inability to test original bytes across tools.
3. Record source URL, race ID, response body complete UTC/JST time, raw byte length/SHA256, HTTP status, source content type and parser version. Never claim source publication time, true first-ever observation, immutable DB write or predeadline odds.
4. Independently compare the exact original `raceresult` page's **3連単 ticket/payout** with `返還` section/absent status and F/L statuses. If official markup differs, fail closed with a precise layout gap. Do not infer refunds from F/L alone; if whole race or 3連単 invalid, do not treat as a normal payout.
5. Emit an anonymous minimal report with section presence and count of refundable boats, parser discrepancy and hard-hold flags. Preserve no racer names or registration IDs in logs. Defer any permanent raw storage to separate signed-off source/retention design.

## Promotion prohibitions
- A matching original archived result establishes at most **one postrace sample's content parity**, not independently authenticated receipt, real ticket-level refund rule for all race types, nor as-of V5 candidate/odds evidence. All `selection_eligible`, `forward_eligible`, `buy_eligible` remain false. No real ROI or auto-purchase.
- For V5 economic evaluation, later separately capture genuine 120-ticket original **predeadline** odds, frozen exact V5 selection/tickets/stakes and independently source-bound real results/refunds. Include VOID/F-L in original cohort; mark missing as PENDING instead of fabricating money.

**Nonnegotiables:** V5 future monthly net profit target +JPY50,000 is unverified; about 1–3 selective races/day or zero. ChatGPT + Railway ≤JPY6,000/month, ideally ≤JPY5,000; Railway aim USD10–12, warning USD15, next invoice ≤USD20 target. No Railway cost from this design.
