# V5 current compact pointer — 2026-10-26
Active handoff: `docs/LIVE_HANDOFF_20261026_V5_PAPER_READINESS_COMPACT.md`
Design: `docs/V5_DIRECT_PRIMARY_LEGACY_FALLBACK_PARALLEL_DESIGN_20261026.md`
New chat: read this + active handoff + `docs/NEXT_CHAT_START_HERE.md`; no old handoff bulk loading.

Decision: V5 will be PRIMARY direct official collector to `boat_data_stage.*`, legacy collector temporarily SECONDARY into separate `public.v2_*` only. No parallel writes to identical table, no stopping legacy before verified canary/rollback.
GitHub now contains pure `v5/direct_shared_primary_routes.py` (fixed 13 stage physical targets, fail-closed canary) and `tests/test_v5_direct_shared_primary_routes.py` (10 offline tests). **No live V5 direct collection, no deployed switch, tests not yet executed.** Earlier existing V5 forward script still calls legacy v21 collector, old route defaults are intact.
**Next ONE task:** run only `python -m unittest discover -s tests -p 'test_v5_direct_shared_primary_routes.py' -v` in an updated working tree/offline test environment; review result, then use guarded canary route in native V5 writer after matching source/stage schemas and confirming writer/reader isolation. No write-mode flags/timer changes yet.
2025-07..2026-09 15-month stage race+entry consistency internal PASS only; Oct 26 144 stage-missing races (12 venues×12), source-vs-stage diagnostic `deploy/conoha/v5_today_entries_source_vs_stage_readonly_20261026.sql` prepared but NOT run. Current V5 inference/BUY not validated. Existing 2026-10-27 03:05 stage11 timer not altered. ConoHa local PG database is named `railway`, Railway cloud unused. Preserve collectors, buy OFF and backups deferred.
