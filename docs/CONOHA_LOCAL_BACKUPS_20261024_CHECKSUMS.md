# ConoHa local DB backups — 2026-10-24 checksum baseline

These checksums are from screenshots of **read-only** shell commands on ConoHa. They identify local bytes at the time of hashing, not an independent off-server copy or a guarantee of live-DB freshness.

| Database | Local backup path | Bytes | SHA-256 |
|---|---|---:|---|
| railway | `/var/backups/boat-railway-20261023-ORfLpY/railway.dump` | 393138215 | `4ee6a5d9c1ddf67c61b8bb82426961431c25f20f944f87b6cef5137bb294478d` |
| boat_history_archive | `/var/backups/boat-history-20261024-U6CRLt/boat_history_archive.dump` | 81865791 | `7301975821593cdab2fdcf30eedc8d78558537023ed7af30f03d679de19fd37e` |

## Verified scope
- railway dump: created 2026-10-23 19:32 JST; limited isolated restore of `public.v2_venues` 24 rows passed. Full railway restoration still **not** verified.
- archive dump: created 2026-10-24 08:28 JST; TOC read passed, full isolated restore of three user tables passed and the temporary DB was removed, and TOC/live user **table names** matched. Full data content/row-count parity **not** verified.
- archive SHA-256: 08:37 JST terminal screenshot with success marker `ARCHIVE_SHA256_READ_ONLY_PASS`; initial hand-entered archive path typo `U6CRtL` was corrected to `U6CRLt` by glob discovery.
- railway SHA-256: 10:58 JST terminal screenshot with success marker `RAILWAY_SHA256_READ_ONLY_PASS`; filename was selected using one-match glob and verified.
- The two files are on the same ConoHa VPS, **not an independent off-server backup**. Google Drive `v5_gdrive:` had HTTP 403 `RATE_LIMIT_EXCEEDED` on 00:09 JST; Drive identity/independent destination not confirmed; no upload, overwrite, or Drive restore has occurred.

## External preservation release gate (not yet satisfied)
1. Identify a clearly separate V5-only remote directory/new generation without modifying V3/V4 backups, and establish destination identity/access only when API limits safely permit. Different rclone refresh tokens do not prove separate Google accounts.
2. Upload as **new immutable generation** with explicit file names and no overwrite, and include this checksum manifest. Guard API rate/transfer/CPU to protect existing collector and costs. Never claim success from mere API connection.
3. Validate each remote object's length and SHA-256 **of the actual retrieved bytes**, not merely metadata, ideally by downloading into an independently controlled test environment. Perform an isolated restore and confirm relevant data. Document cleanup and retention.
4. Until verified: preserve both local dumps, existing `boat_data_stage.venues` 24-row stage, the thirteen VIEWs and all legacy source/writer paths. **Production physical cutover 0/13, NO-GO; BUY disabled.**

**Fail-closed external backup plan**: [V5_EXTERNAL_BACKUP_FAIL_CLOSED_PLAN_20261024.md](V5_EXTERNAL_BACKUP_FAIL_CLOSED_PLAN_20261024.md) — designed on GitHub 2026-10-24; no transfer or independent restore yet. **Next one task:** prepare a V5 runtime backup inventory checklist on GitHub only (code/versions/systemd/configuration evidence, no secrets). Do not call Google Drive or modify ConoHa until separately approved.
