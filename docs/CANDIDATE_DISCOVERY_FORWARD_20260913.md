# Candidate Discovery Forward Freeze — 2026-09-13 JST

Research-only prospective freeze for the new Candidate Discovery main feed.

## Freeze identity

- PR: #351
- Branch: `research/candidate-discovery-v1-20260913`
- Commit: `53506eb88e37c51b1ce9d102c44bcbe2c0fb59f3`
- GitHub Actions run: `34726186753`
- Artifact: `candidate-discovery-main-feed-34726186753`
- Artifact ID: `10308110102`
- Artifact ZIP SHA-256: `3930d272fa826d907454e418f4800b3018c4fda9246933f40351311e9bfe3236`
- Freeze execution time: 2026-09-13 08:44 JST (GitHub log time 2026-09-12 23:44 UTC)

## Input readiness

- scheduled races: 180
- evaluable races: 180
- incomplete-entry skips: 0
- core races: 6
- legacy shadow rows present at freeze time: 2
- feed races: 8
- feed tickets: 14
- Motor2-supported tickets: 11

The feed was generated inside an explicit read-only PostgreSQL transaction. No DB write, LINE send, purchase action, Production selector change, or Railway config change was performed.

## Frozen feed

### Tier A

1. `20260913_11_02` / venue 11 / R02
   - `2-3-5`
   - `2-3-1`
2. `20260913_08_08` / venue 08 / R08
   - `2-3-6`
   - `2-6-3`

### Tier B

3. `20260913_22_03` / venue 22 / R03
   - `3-4-5`
   - `3-5-4`
4. `20260913_19_05` / venue 19 / R05
   - `1-4-3`
   - `1-4-5`

### Tier C

5. `20260913_07_07` / venue 07 / R07
   - `1-3-4`
   - `1-4-3`
6. `20260913_08_05` / venue 08 / R05
   - `2-5-1`
   - `2-1-5`

### Legacy carryover present at freeze time

- `20260913_10_01` / venue 10 / R01 — `1-6-5`
- `20260913_21_01` / venue 21 / R01 — `3-1-2`

## Evaluation rule

Do not regenerate or alter this candidate set after race results are known. Evaluation must use this exact frozen feed/artifact. Later legacy candidates, if generated after this freeze, are separate observations and must not be retroactively added to this 08:44 JST freeze.

`purchase_action=false` remains mandatory.
