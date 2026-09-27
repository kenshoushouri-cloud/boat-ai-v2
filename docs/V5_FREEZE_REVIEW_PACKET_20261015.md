# V5 freeze review packet — pure review-only contract

Target milestone:
- 2026-10-15 V5 core research-candidate freeze review.

This packet builder exists so the project does not need a new ad hoc analysis script when the evidence gates mature.

Input:
- one already-generated combined Forward checkpoint JSON;
- optional day-strength summary JSON.

The packet copies and standardizes:
- V4 resolved formal days;
- V4 TOP2 economics and robustness;
- S03_M2 coverage/economics/risk/halves/bootstrap;
- V5 core milestone state;
- optional-layer admission state.

It may expose descriptive booleans such as `ROI > 100%`.

Those booleans are **not automatic promotion rules**.

When the V5 core evidence gates are reached, the packet status becomes:
`CORE_EVIDENCE_READY_FOR_HUMAN_FREEZE_REVIEW`.

It still requires a deliberate research review to choose what, if anything, becomes the frozen V5 research candidate.

Never automatic:
- Production activation;
- model coefficient change;
- selector change;
- stake change;
- LINE;
- purchase.

Optional day-strength remains nonblocking:
- admission requires >=10 future resolved days, >=3 KEEP and >=3 SKIP;
- otherwise it remains shadow-only.

F-count remains separately approval-gated and is not inferred by this packet.

`PURE_REVIEW_PACKET / NO_AUTO_DECISION / NO_PRODUCTION_ACTIVATION / PURCHASE_FALSE`
