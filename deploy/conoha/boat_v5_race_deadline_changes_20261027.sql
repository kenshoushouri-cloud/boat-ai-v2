-- boat_data_stage.race_deadline_changes: 締切同期(v5.native_deadline_sync)の履歴表。
-- 2026-10-27 に承認のうえ本番で作成済み。このファイルは記録用で、自動実行しない。
-- 作成:  sudo -u postgres psql -X -v ON_ERROR_STOP=1 railway -f <this file>
-- 注意: 既に表がある本番では実行しない(IF NOT EXISTS は付けていない)。
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '5s';

CREATE TABLE boat_data_stage.race_deadline_changes (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  race_id        text        NOT NULL,
  race_date      date        NOT NULL,
  old_deadline   timestamptz NOT NULL,
  new_deadline   timestamptz NOT NULL,
  old_time_text  text,
  new_time_text  text        NOT NULL,
  delta_minutes  integer     NOT NULL,
  source         text        NOT NULL DEFAULT 'official_racelist_table',
  captured_at    timestamptz NOT NULL,
  applied_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT race_deadline_changes_changed  CHECK (new_deadline <> old_deadline),
  CONSTRAINT race_deadline_changes_delta    CHECK (delta_minutes BETWEEN -60 AND 60),
  CONSTRAINT race_deadline_changes_time_fmt CHECK (new_time_text ~ '^[0-2][0-9]:[0-5][0-9]$')
);
CREATE INDEX race_deadline_changes_race_idx
  ON boat_data_stage.race_deadline_changes (race_id, applied_at);
CREATE INDEX race_deadline_changes_date_idx
  ON boat_data_stage.race_deadline_changes (race_date);

COMMIT;
