#!/usr/bin/env bash
# Non-persistent PostgreSQL DDL REHEARSAL (CREATE inside a transaction, ROLLBACK).
# Stage12 physical objects exist temporarily inside the transaction, but are
# NOT committed. Never runs a production cutover, data COPY or service STOP.
# All source/venue tables remain untouched. Abort on any unexpected token.
set -euo pipefail
umask 077
export LC_ALL=C
R=/opt/boat-ai-v5
T=$(mktemp -d /tmp/v5_stage_ddl_rehearsal_XXXXXXXX)
trap 'rm -rf -- "$T"' EXIT

# Input is exactly the pinned, previously fetched GitHub revision (FETCH_HEAD).
for x in \
 "boat_shared_storage_contract.py" \
 "v5/offline_stage_batch_plan.py" \
 "deploy/conoha/v5_stage_12_bootstrap_guarded.py"
do
  mkdir -p "$T/$(dirname "$x")"
  git -C "$R" show "FETCH_HEAD:$x" > "$T/$x"
done

PYTHONPATH="$T" PYTHONDONTWRITEBYTECODE=1 python3 -B \
 "$T/deploy/conoha/v5_stage_12_bootstrap_guarded.py" --plan \
 > "$T/proposed.txt"

test "$(head -n 1 "$T/proposed.txt")" = "V5_EMPTY_STAGE_12_SQL_PLAN_ONLY_NO_DB_ACCESS" || {
  echo "NO_GO_UNKNOWN_PLAN_FORMAT"; exit 2;
}
tail -n +2 "$T/proposed.txt" > "$T/sql.txt"
test "$(grep -c '^COMMIT;$' "$T/sql.txt")" = 1 || {
  echo "NO_GO_NOT_EXACTLY_ONE_COMMIT"; exit 2;
}
test "$(grep -c '^CREATE TABLE ' "$T/sql.txt")" = 12 || {
  echo "NO_GO_NOT_EXACTLY_TWELVE_CREATE"; exit 2;
}
test "$(grep -c '^BEGIN;$' "$T/sql.txt")" = 1 || {
  echo "NO_GO_TRANSACTION_SCOPE"; exit 2;
}
! grep -Eq '^(INSERT |UPDATE |DELETE |DROP |TRUNCATE |ALTER |COPY |\\!|\\copy )' "$T/sql.txt" || {
  echo "NO_GO_FORBIDDEN_SQL"; exit 2;
}
# Change COMMIT to ROLLBACK before sending anything to PG.
sed -e 's/^COMMIT;$/ROLLBACK;/' \
    -e "s/V5_EMPTY_STAGE_12_CREATED_NO_ROWS_NO_CUTOVER/V5_EMPTY_STAGE_12_REHEARSAL_ROLLBACK_NO_ROWS_NO_CUTOVER/" \
 "$T/sql.txt" > "$T/rollback.sql"
! grep -q '^COMMIT;' "$T/rollback.sql" || {
  echo "NO_GO_SQL_STILL_CONTAINS_COMMIT"; exit 2;
}
# A failing psql command closes the connection, rolling back transaction.
echo "=== V5 12 EMPTY STAGE TRANSACTION ROLLBACK REHEARSAL ==="
timeout -k 3s 65s \
 runuser -u postgres -- \
 psql -X -P pager=off -v ON_ERROR_STOP=1 -d railway \
 < "$T/rollback.sql" > "$T/result.log" || {
    echo "V5_STAGE_12_REHEARSAL_STOPPED_OR_ROLLED_BACK"; exit 1;
 }
if ! grep -q 'V5_EMPTY_STAGE_12_REHEARSAL_ROLLBACK_NO_ROWS_NO_CUTOVER' "$T/result.log"; then
  echo "NO_GO_REHEARSAL_MARKER_NOT_FOUND"; exit 2
fi

# Second independent read-only transaction checks that no stage was retained.
cat > "$T/verify.sql" <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout='8s';
WITH targets(name) AS (
 VALUES
 ('boat_data_stage.races'),('boat_data_stage.entries'),
 ('boat_data_stage.results'),('boat_data_stage.racer_results'),
 ('boat_data_stage.trifecta_odds'),
 ('boat_data_stage.exhibition_snapshots'),
 ('boat_data_stage.racer_course_stats_snapshots'),
 ('boat_data_stage.entry_snapshots'),('boat_data_stage.odds_snapshots'),
 ('boat_data_stage.weather_snapshots'),
 ('boat_data_stage.race_condition_snapshots'),
 ('boat_data_stage.racer_condition_snapshots')
)
SELECT count(*) AS missing_all_12_after_rollback
FROM targets WHERE to_regclass(name) IS NULL;
SELECT CASE WHEN to_regclass('boat_data_stage.venues') IS NOT NULL
 THEN 'VENUES_STAGE_PRESERVED' ELSE 'STOP_VENUES_STAGE_MISSING' END AS check;
ROLLBACK;
SQL
timeout -k 2s 20s \
 runuser -u postgres -- \
 psql -X -At -P pager=off -v ON_ERROR_STOP=1 -d railway \
 < "$T/verify.sql" > "$T/verify.log"
if ! grep -qx '12' "$T/verify.log" || \
   ! grep -qx 'VENUES_STAGE_PRESERVED' "$T/verify.log"; then
  echo "NO_GO_STAGE_NOT_FULLY_ROLLED_BACK"; exit 2
fi
echo "V5_12_EMPTY_STAGE_DDL_REHEARSAL_ROLLBACK_PASS"
echo "STAGES_CREATED_PERSISTENTLY=0"
echo "COLLECTION_UNCHANGED=YES"
echo "PRODUCTION_CUTOVER=NO_GO"
