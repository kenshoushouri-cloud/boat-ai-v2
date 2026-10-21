#!/usr/bin/env bash
# 2026-10-17 K race recovery: short, guarded Termius entry point.
# Usage: bash deploy/conoha/k17_recover_short_20261021.sh 63 [apply]
# Without "apply", strict read-only preview only.
set -euo pipefail
cd /opt/boat-ai-v5
EXPECTED="${1:-}"
MODE="${2:-preview}"
if [[ ! "$EXPECTED" =~ ^[0-9]{1,3}$ ]] || (( 10#$EXPECTED < 51 || 10#$EXPECTED >= 168 )); then
  echo "STOP: expected race count must be 51..167"; exit 1
fi
if [[ "$MODE" != "preview" && "$MODE" != "apply" ]]; then
  echo "STOP: mode must be preview or apply"; exit 1
fi
if [[ ! -f deploy/conoha/k_missing_races_bounded_runner_20261021.py ]]; then
  echo "STOP: bounded runner not installed"; exit 1
fi
DB_STATS() {
  runuser -u postgres -- psql -XAt -v ON_ERROR_STOP=1 -d railway -c "
WITH x AS (
 SELECT r.race_id,count(e.lane) AS n,count(DISTINCT e.lane) AS lanes
 FROM public.v2_races r
 LEFT JOIN public.v2_race_entries e ON r.race_id=e.race_id
 WHERE r.race_id >= '20261017_' AND r.race_id < '20261018_'
 GROUP BY r.race_id
)
SELECT count(*)::text || ':' || coalesce(sum(n),0)::text || ':' ||
 count(*) FILTER (WHERE n<>6 OR lanes<>6)::text || ':' ||
 (SELECT count(*) FROM public.v2_results
  WHERE race_id >= '20261017_' AND race_id < '20261018_')::text
FROM x;"
}
EXPECTED=$((10#$EXPECTED))
WANT="${EXPECTED}:$((EXPECTED*6)):0:$((EXPECTED-1))"
BEFORE="$(DB_STATS)"
echo "BEFORE=$BEFORE EXPECTED=$WANT"
if [[ "$BEFORE" != "$WANT" ]]; then
  echo "STOP: database differs; no work started"; exit 1
fi
if [[ "$MODE" == "preview" ]]; then
  runuser -u postgres -- env HTTP_TIMEOUT=30 HTTP_MAX_RETRIES=0 \
    /opt/boat-ai-v5-venv/bin/python \
    deploy/conoha/k_missing_races_bounded_runner_20261021.py \
    --day 2026-10-17
  [[ "$(DB_STATS)" == "$WANT" ]] || { echo "STOP: DB changed during preview"; exit 1; }
  echo "SHORT_PREVIEW_OK_NO_DB_WRITES"
  exit 0
fi
# One six-race batch only; worker still requires both independent apply gates.
nice -n 10 runuser -u postgres -- env \
  CONFIRM_V5_K_RACE_REPAIR=YES HTTP_TIMEOUT=30 HTTP_MAX_RETRIES=0 \
  /opt/boat-ai-v5-venv/bin/python \
  deploy/conoha/k_missing_races_bounded_runner_20261021.py \
  --day 2026-10-17 --batches 1 --apply
AFTER="$(DB_STATS)"
TARGET="$((EXPECTED+6)):$(((EXPECTED+6)*6)):0:$((EXPECTED+5))"
echo "AFTER=$AFTER EXPECTED=$TARGET"
[[ "$AFTER" == "$TARGET" ]] || { echo "STOP: postcheck mismatch; do not rerun"; exit 1; }
echo "SHORT_BATCH_VERIFIED"
