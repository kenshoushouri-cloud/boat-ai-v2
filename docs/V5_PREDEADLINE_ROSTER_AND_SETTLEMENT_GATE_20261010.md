# V5 — 締切前6艇情報と結果確定の分離（2026-10-10）

**Status:** V5-only paper-shadow evaluation design, NOT production permission. No fresh live official race GET, Railway/DB/CI, LINE, stakes, BUY or V4 changes in this task.

## Decision: V4 is not a required model/economic comparison
- V5 was commissioned because V4 actual profitability was poor. **V4-vs-V5 head-to-head comparison is OPTIONAL historical diagnosis, NOT a V5 production acceptance gate** and must not delay V5.
- V5 acceptance instead requires its **own**, on-frozen-eligible-cohort 2025-07 onward retrospective assessment where true as-of evidence exists, plus predeadline prospective paper-shadow trials: complete 3連単 odds and official result/refunds, net yen, ROI, ticket-hit rate, number of selected races and tickets, losing streak, drawdown, uncertainty/holdout, cost and operational reliability. When historic timestamps/odds are mutable or missing, tag NOT_ASOF and do not mix with independently frozen prospective evidence.
- Objective: ~1–3 quality candidates/day or zero, eventual **monthly net +JPY50,000** (unverified aspirational, not profit guarantee), purchase points/stakes not approved.

## New two-stage distinction
### A. Before race deadline — observable entrants, NEVER proven actual starters
For **shadow (zero real purchases)** only, candidate may proceed with a *labelled unverified* cohort if ALL:
1. Exact day/venue/race ID and six unique lane↔racer registrations from race-specific **official racelist**; reject duplicate/missing/ambiguous.
2. Matching beforeinfo/exhibition identity for all six lanes; explicitly reject displayed withdrawals/出走取消, or incomplete exhibition; **absence of a withdrawal notice is negative evidence, NOT positive confirmation**.
3. The originally observed bytes/digest and accurate acquisition-completion timestamp are captured and **frozen before a verified race-specific decision cutoff**, with later edits prohibited; record source version and any historical provenance limitation. Reusing a mutable historical UPSERT time as first observation is forbidden. Official publisher release time and independently audited immutable first write remain distinct unknowns unless actually proved.
4. Exact race-bound observed official 3連単 odds are present with complete 120-ticket original-byte parity where possible. Otherwise keep no-price / NO_ECONOMIC_EVIDENCE; never invent odds from retrospective snapshots.
5. All missing/late/stale/contradictory records are `SHADOW_INELIGIBLE_DATA_GAP`, not implicit winners or missing-at-random filters.
6. Status may be `SIX_LISTED_EXHIBITION_OBSERVED_ONLY` for **paper shadow**, but `six_active_starts_confirmed`, `beforeinfo_first_write_eligible`, `forward_eligible`, `selection_eligible` for real selection and `buy_eligible` ALL remain **FALSE**. In particular, do NOT remove existing live `BEFOREINFO_PRE_HTTP_HARD_HOLD`.

**Why:** BOAT RACE official guide defines 欠場 in circumstances including start-time F/L and other failures; such events are not decidable before the start. Therefore requiring knowledge of six **actual successful starts** before placing a prediction conflates future outcome with obtainable as-of evidence. For prospective offline research, record predeadline scheduled/observed six without claiming they actually started.

### B. After race — adjudication and immutable economic cohort
- Official confirmed OFFICIAL / VOID / refund / F-L and race result/payouts are observed **after** race as distinct records. Results never leak into predeadline features, gate, ticket order, or sample inclusion.
- Denominator = ALL predecision candidates with frozen proposed mock purchases, including subsequent VOID, F/L, refunds and losing races. Do NOT silently filter early K VOID, zero-entrant or missing official K outcomes; unresolved result gets `PENDING`, and report partial result coverage not invented ROI.
- Cash = sum(final official payout and refunds) - sum(hypothetical original stake), with ticket-by-ticket settlement and costs stated separately. Odds at predecision and postrace final odds are different observations. Paper-ledger calculations are not proof of actual betting or profit.
- Split `as-of eligible/paper`, `historical not-as-of`, `settlement unresolved`, and eventual `independently authenticated/live-verified` cohorts. No promotion from retrospective or fictional receipts.

## External official source review (general guidance, not a new race GET)
- Official BOAT RACE guide「欠場」: https://www.boatrace.jp/owsp/sp/extra/enjoy/guide/jiten/09/y_060.html ; reasons include start-time incidents and associated ticket refunds.
- Official BOAT RACE guide「返還」: https://www.boatrace.jp/owsp/sp/extra/enjoy/guide/jiten/29/y_250.html ; F/L at the start is refunded; post-start incidents are treated differently.
- Official BOAT RACE guide「返還欠場」: https://www.boatrace.jp/owpc/pc/extra/enjoy/guide/jiten/29/y_251.html .
- Official race list and beforeinfo pages display scheduled boat/racer identifiers and exhibition fields, **not an independently verified published affirmative per-lane proof** that every boat will start; a published source schema proving that was NOT found from these general guides. No race-specific fresh diagnostic run occurred.
- `docs/V5_POSITIVE_START_DIAGNOSTIC_DESIGN_20261010.md` retains the opt-in restrictions for any future bounded race-specific live diagnostic. `APPROVED_POSITIVE_SOURCE_SCHEMAS` remains empty; no automatic live GET or V5 purchase approval.

## Next implementation priority
1. Adopt V5-only **paper-shadow** roster/date/cutoff status vocabulary and day cohort acceptance as above without modifying live pre-HTTP beforeinfo, source allowlists, DB/DDL or BUY flags.
2. Verify real frozen predeadline 3連単 odds and postrace results/refunds through budget-bounded observation only after proper review/permission; distinguish first-observation authenticity. Estimate **V5-only** ROI with proper abstention and unresolved coverage.
3. Independently review eventual real purchase eligibility based on as-of predictable evidence and automatic payout/refund controls, not an impossible guarantee of future F/L absence. Separate explicit approval needed.
4. After V5 cutover is actually proven safe, stop V4, archive 2025-07 historical data with restore/parity and decommission redundant Railway services only on permission.

**Nonnegotiable budgets:** combined ChatGPT+Railway <=JPY6,000/month, ideally <=JPY5,000; Railway aim USD10–12, warn USD15, next invoice ceiling USD20 target. No extra Railway usage created by this design note.
