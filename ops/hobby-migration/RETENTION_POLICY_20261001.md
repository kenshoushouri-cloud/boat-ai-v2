# Hobby Retention Policy — 2026-10-01

Status: **FINALIZED FOR MIGRATION PREP**  
Mode: **FULL_HISTORY_PINNED**

## Decision

For the initial Pro -> Hobby migration candidate, keep the full PostgreSQL dataset. Do **not** delete historical rows before historical matched-readiness and matched-contract backtest are complete.

Space reduction for the initial Hobby candidate must come from a fresh logical restore/compaction, not historical-row deletion.

## Evidence

Read-only finalization run: `36813600010`  
Evidence artifact: `hobby-retention-finalization-36813600010` / id `11139948972`  
Evidence SHA-256: `671c9044250cd791061fe4c516a8263591a2dad83302a6c1f74a64b2c4f8273d`

- Production database snapshot: **4,437,243,583 bytes**
- Exact-parity fresh full restore baseline: **3,615,987,391 bytes**
- Estimated next-14-day date-addressable growth: **418,466,615 bytes** (planning estimate)
- Projected fresh full restore + 14d growth: **4,034,454,006 bytes**
- Planning headroom against 5,000,000,000 bytes: **965,545,994 bytes**
- 60d removal from the five previously proposed hot-only tables would remove about **2,171 MiB**
- 90d removal would remove about **1,979 MiB**
- Labeled historical rows affected: **843,072 at 60d / 776,676 at 90d**

The historical matched-contract readiness path reads historical weather/exhibition evidence back to 2025-07-01. Deleting those rows now would break the planned research path.

## Guardrails

- No Production historical DELETE before matched-readiness and matched-contract backtest complete.
- No use of the existing 60d filtered candidate as a cutover reference.
- The next Hobby-compatible candidate must be a fresh full-history restore onto a 5 GB-compatible volume.
- Require read-only parity and adequate free-space headroom before any cutover approval.
- If projected/actual headroom falls below **500 MB**, stop and re-evaluate retention before cutover.
- After historical matched-contract work completes, re-run retention sizing; evaluate **90d before 60d** for the five high-volume raw tables.
- Any later deletion remains a separate destructive action requiring explicit approval.
- `purchase_action=false`.

## Next single task

Create/prepare a **Hobby-compatible 5 GB full-history DB/volume candidate**, restore the current recovery reference into it, then verify read-only parity before any cutover.

`FULL_HISTORY_PINNED / COMPACTION_NOT_DELETE / PARITY_BEFORE_CUTOVER / 500MB_HEADROOM_GUARD`
