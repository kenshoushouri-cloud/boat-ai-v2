# V4 fallback timing margin — preregistered design, 2026-09-27

## Scope

Pure timing design only. **No Railway Cron change is made by this Draft.**

Current contract:
- source cutoff: 08:15 JST
- primary nominal GitHub schedule: 08:16 JST
- Railway fallback Cron: 08:25 JST

Recent fallback formal captures on 2026-09-23..09-27 all succeeded, but completion-to-earliest-feed headroom reached only about 81 seconds on the narrowest day.

## Frozen observed evidence

Using the actual formal freeze completion time and earliest feed deadline:

| Date | Freeze complete JST | Earliest feed deadline | Actual headroom |
|---|---:|---:|---:|
| 09-23 | 08:28:46.600 | 08:44:00 | 913.400 s |
| 09-24 | 08:30:35.347 | 08:32:00 | 84.653 s |
| 09-25 | 08:28:50.234 | 08:32:00 | 189.766 s |
| 09-26 | 08:30:39.396 | 08:32:00 | 80.604 s |
| 09-27 | 08:29:31.876 | 08:32:00 | 148.124 s |

Observed Railway dispatcher log times also show the 08:25 Cron did not execute exactly at 08:25:
- 09-23: 08:28:28.339
- 09-24: 08:27:37.427
- 09-25: 08:26:32.319
- 09-26: 08:28:09.929
- 09-27: 08:27:00.444

So schedule-to-dispatch jitter was approximately 92..208 seconds.

## Counterfactual method

Do **not** assume faster GitHub or Railway execution.

For each candidate Cron time, keep each observed 08:25-schedule -> freeze-complete latency unchanged and shift only the scheduled checkpoint earlier. This is conservative relative comparison, not a guarantee of future latency.

Candidates are frozen before any Production change:
- 08:18
- 08:20
- 08:22
- 08:25 current

## Frozen safety criteria

A candidate passes only if all are true:

1. scheduled at least 5 minutes after the 08:15 source cutoff;
2. scheduled at least 4 minutes after the nominal 08:16 primary;
3. under all five observed latencies, projected worst completion remains at least 5 minutes before the earliest feed deadline.

Result:

| Candidate | cutoff gap | primary gap | projected worst feed headroom | Pass |
|---|---:|---:|---:|---|
| 08:18 | 3m | 2m | ~8m21s | No |
| **08:20** | **5m** | **4m** | **~6m21s** | **Yes** |
| 08:22 | 7m | 6m | ~4m21s | No |
| 08:25 | 10m | 9m | ~1m21s | No |

Therefore the preregistered preferred candidate for a **separate explicit Production approval** is:

**08:20 JST / Cron `20 23 * * *` UTC**

## Why not 08:18

It has more deadline margin, but it fires only two minutes after the nominal primary and three minutes after source cutoff. That creates unnecessary duplicate-dispatch pressure and gives the primary too little observation time.

## Why not 08:22

It preserves more primary observation time, but does not satisfy the frozen five-minute worst-case feed-margin target using the observed latency set.

## Production boundary

This Draft does not:
- change Railway Cron;
- redeploy a timing change;
- change the 08:15 source cutoff;
- change the primary schedule;
- change arbitration;
- change V4 model/selector/TOP6/TOP2/stake;
- send LINE;
- enable purchase.

Actual Cron change from `25 23 * * *` to `20 23 * * *` requires explicit user approval in a separate action.

`PREFERRED_FOR_SEPARATE_APPROVAL_0820 / NO_CRON_CHANGE / NO_PROD_CHANGE / PURCHASE_FALSE`
