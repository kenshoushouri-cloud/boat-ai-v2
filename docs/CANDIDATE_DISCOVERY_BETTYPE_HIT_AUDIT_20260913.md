# Candidate Discovery — Bet-Type Hit-Rate Audit (2026-09-13)

Research-only historical comparison. This checkpoint freezes the observed hit-rate geometry **before multi-bet payout/ROI results are used to choose a purchase strategy**.

## Contract

Period: `2025-07-01..2026-09-12`

Historical selection baseline:
- Candidate Discovery V2 structural race ranking
- `MOTOR2_FACTOR` probability variant for primary comparisons
- race selection uses no odds, EV, or payout
- official result is read only after the race/ticket selections are frozen in memory

Bet types derived from the same 120-ticket trifecta distribution:
- trifecta / 3連単: 120 exact-order combinations
- exacta / 2連単: `P(a-b) = sum_c P(a-b-c)`; 30 combinations
- trio / 3連複: unordered top-three probability = sum of six order permutations; 20 combinations

Point strategies were predeclared:
- fixed: TOP1 / TOP2 / TOP3 / TOP5
- probability coverage: 20% / 35% / 50%, capped at 12 tickets
- flat reference unit: 100 JPY per selected ticket

This audit evaluates hit rate and losing streaks only. It does **not** establish profitability.

## Primary comparison — top 6 races/day

Evaluated selected races: `2,608`.

| bet type | TOP1 hit | TOP2 hit | TOP3 hit | TOP5 hit | TOP1 max losing streak | TOP5 max losing streak |
|---|---:|---:|---:|---:|---:|---:|
| 3連単 | 8.627% | 16.334% | 22.584% | 31.979% | 115 | 18 |
| 2連単 | 19.977% | 34.701% | 47.354% | 63.113% | 30 | 6 |
| 3連複 | 29.410% | 48.160% | 60.890% | 76.994% | 24 | 6 |

Coverage views:
- 2連単 20% coverage: avg 2.785 points, hit 45.169%, max losing streak 12
- 2連単 35% coverage: avg 4.889 points, hit 62.117%, max losing streak 11
- 2連単 50% coverage: avg 7.772 points, hit 76.495%, max losing streak 6
- 3連単 20% coverage: avg 7.909 points, hit 43.558%, max losing streak 12
- 3連単 35% coverage: avg 11.982 points, hit 55.368%, max losing streak 8
- 3連複 20% coverage: avg 1.959 points, hit 47.469%, max losing streak 11
- 3連複 35% coverage: avg 3.199 points, hit 63.113%, max losing streak 6
- 3連複 50% coverage: avg 4.940 points, hit 76.342%, max losing streak 6

## A / B / C tier comparison — top 6 races/day

Tier contract:
- A = daily structural rank 1-2
- B = daily structural rank 3-4
- C = daily structural rank 5-6

Evaluated races: A `866`, B `868`, C `874`.

### A tier

| bet type | TOP1 | TOP2 | TOP3 | TOP5 |
|---|---:|---:|---:|---:|
| 3連単 | 10.046% | 17.321% | 24.827% | 34.527% |
| 2連単 | 22.286% | 37.067% | 50.346% | 65.242% |
| 3連複 | 31.871% | 49.423% | 62.009% | 78.406% |

### B tier

| bet type | TOP1 | TOP2 | TOP3 | TOP5 |
|---|---:|---:|---:|---:|
| 3連単 | 9.677% | 16.475% | 23.272% | 32.949% |
| 2連単 | 20.161% | 36.521% | 49.770% | 65.323% |
| 3連複 | 31.452% | 50.461% | 63.940% | 79.493% |

### C tier

| bet type | TOP1 | TOP2 | TOP3 | TOP5 |
|---|---:|---:|---:|---:|
| 3連単 | 6.178% | 15.217% | 19.680% | 28.490% |
| 2連単 | 17.506% | 30.549% | 41.991% | 58.810% |
| 3連複 | 24.943% | 44.622% | 56.751% | 73.112% |

## Interpretation frozen before ROI work

1. 3連複 materially improves hit rate and reduces losing streaks at modest point counts.
2. 2連単 is a meaningful middle ground between 3連単 payout potential and 3連複 hit stability.
3. A/B have similar hit geometry. C is weaker, especially for exact-order bets; 3連複 retains comparatively strong hit coverage in C.
4. These observations justify a later **mixed bet-type** profitability study, but do not justify choosing a final A/B/C purchase recipe yet.
5. The next decision must use official realized payouts with the same predeclared candidates and 100-yen-per-ticket accounting. Do not select a strategy from hit rate alone.

## Safety / status

- DB write: 0
- LINE: 0
- BUY: 0
- Production change: 0
- payout ROI: pending official multi-bet payout parser verification

`RESEARCH_ONLY / HIT_RATE_EVIDENCE_ONLY / NO_PROFITABILITY_CLAIM / PURCHASE_ACTION_FALSE`
