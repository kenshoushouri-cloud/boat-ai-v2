# V5 compact handoff — 2026-10-24 17:10 JST
Repo: `kenshoushouri-cloud/boat-ai-v2`. THIS is the current compact handoff; long `LIVE_HANDOFF_20261023_0651_COMPACT.md` is archived reference ONLY. Do not bulk-read it, old handoffs or history. SHA, sizes, runtime state and counts are not permanent; check live only as needed for one task.

## Goal and priorities
V5 boat racing AI (primary), reuse existing V5 research/forecast code; use data since 2025-07, test valuable features without silent hindsight. Goal late Oct **non-buy limited trial**, not guaranteed. Actual buy disabled pending separate proof/approval. Next priorities: audit source coverage, establish trustworthy predecision inputs, reconcile V5 model T1.00 strong-core vs previous T2.20 scope-lock (unresolved), integrate existing scorer, as-of receipts, then real backtest/non-buy trial. No invented ROI.
- Existing components: `v5/offline_mainline_inference.py` (6 boat first-place), `offline_trifecta_shadow_ranking.py` (hypothesis 120 ticket PL), `offline_v5_freeze_bridge.py`, `forward_shadow_freeze.py` (shadow journal), `offline_day_shadow_pipeline.py`, `offline_prior_day_factor_export.py` (13 prior-day Counters). **Reuse; don't rewrite.**
- 10/24 isolated ConoHa `/tmp` synthetic tests: as-of bridge 9/9, shadow writer 6/6, daily modules 3/3 = **18/18 PASS**. Production scorer/first capture/real ROI UNVERIFIED.
- ConoHa `railway` database; `boat_data` 13 non-updatable VIEWs; `boat_data_stage.venues` only 24-row independent first physical stage copy: 1/13. **LIVE physical cutover 0/13 NO-GO**. No DDL/DML/bulk copy/writer or view switch/cron or systemd edits. Main collector from official source actively collecting forward-window. V5 BUY OFF. ConoHa same-host DB/history/code/timer backups+isolated limited restore checked, independent full offsite restore UNVERIFIED. Google Drive `v5_gdrive` new write returned 403 RATE_LIMIT, STOP further writes until controlled recovery, never overwrite V3/V4.
- `snapshot_at<deadline` is not a trustworthy independent first-observation receipt; historic mutable snapshots/postrace features cannot be labeled truly predecision. V5 result on Oct24 Amagasaki 9R `20261024_13_09`: 6 racers, forward label, 6 exhibition, 120 odds, each prior-K5; still `HOLD_UNVERIFIED_FIRST_CAPTURE_AND_MODEL`, 5 real input factor vectors NOT produced.

## Most recent verified result
ConoHa Termius screenshot 10/24 **17:10 JST** ran `deploy/conoha/v5_exhibition_label_coverage_readonly_20261024.sql` for `2026-10-20`, `ROLLBACK` and `V5_EXHIBITION_LABEL_AUDIT_FINISHED`.
- `conoha_forward`: 28 distinct race IDs, 28 labels, 168 rows, **28 complete 6-lane/unique rank**, 28 timestamp-labeled before deadline (NOT first capture proof).
- `other`: one `conoha_timeout_probe_20261020` label, 1 race, six rows, complete six, labeled predeadline; **diagnostic/probe, do NOT train/promote automatically**. Overlap with forward race unknown, do not sum as unique.
- No `historical`/`final_ab`/`learning_all` groups for that day.
- Prior 16:30 research Counter source audit on 10/20: race total144, roster6=144, clean K courses6=132, result present144, **historical-label exhibition complete0**, so current strict training source intersections=0; NOT evidence all labels missing. No data writes.

## Next ONE task
**Read-only PostgreSQL catalog inventory of `boat_history_archive` for possible archived exhibition / beforeinfo / snapshot relations** (names, kind, approx table size only, no data scans), to assess reuse of historical exhibition without scraping/re-fetch. If archive has no relevant relation, next audit existing main DB older dates/months with bounded efficient read-only samples, rather than assume all history missing. No restoration, training, DB/VIEW/collector/Drive write or BUY. Termius ONE command, low resources, short result.

## Work method
Minimal tool calls. GitHub work directly where possible; ConoHa only via copyable code, one short task at a time and user screenshot. Railway CPU/RAM/network/fees minimize (USD15–20 hard concern, cheaper ideal), Railway Agent/AI never. Old docs retained, don't expand this handoff by appending daily narratives.
