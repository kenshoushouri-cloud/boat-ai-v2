# 2026-09-08 odds evidence audit

Status: research-only, no production promotion. Scope is the 19 races reported incomplete at 20:55 JST. This is a plan, not a completed database audit.

The morning and day window logs show successful HTTP/processing calls with incomplete ticket sets. Fetch success is not completeness. The ordinary odds table is updated on race/ticket conflict, so its current fetched_at must not be interpreted as the first observation.

The audit must compare the expected ticket set with the current base table, inspect independently persisted snapshots and their provenance, and distinguish an actual pre-deadline observation from a later reconstruction. It must not fetch historical pages and label their current contents as contemporaneous evidence. Missing evidence is UNKNOWN, not a successful backtest or a reason to loosen the purchase gate.

Implementation: a fixed-date, bounded, SELECT-only diagnostic on a separate branch, with offline tests and a manually invoked workflow. No production Cron, model, LINE, BUY/WATCH/SKIP, database schema, or data changes. No automatic merge. No activation of PR #169.
