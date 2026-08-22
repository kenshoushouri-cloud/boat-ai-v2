# July 2025 historical weather guarded repair

Purpose: review gate for the existing guarded partial-month repair before any explicit database write.

Scope:
- fixed month: 2025-07
- snapshot_label: historical
- fields: temperature_c, water_temperature_c
- source: already-stored official raw.text only
- preserve all existing non-NULL values
- keep the 51 confirmed source-gap races NULL

Required write gates:
1. Read-only repair projection passes.
2. Confirmed 51 source gaps are rechecked against official historical pages immediately before write.
3. No ambiguous parse failures or sanity failures.
4. Write occurs in one transaction and rolls back on any failed postcondition.
5. Historical row count, race_id coverage and raw-text coverage remain unchanged.
6. Nonhistorical rows remain unchanged.

Out of scope:
- exhibition/course/ST/tilt
- Production or Shadow decisions
- LINE notifications
- Railway Variables/settings

After a successful guarded write, rerun the monthly audit and verify that July temperature and water-temperature completeness reaches 5145/5196, with exactly 51 confirmed source gaps remaining NULL.
