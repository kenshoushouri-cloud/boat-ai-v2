-- 実行禁止(承認が要る)。履歴表を削除する。実行前に別途ユーザー承認と、
-- 削除対象行のバックアップ(pg_dump -t boat_data_stage.race_deadline_changes)を取ること。
-- 同期を止めずに削除すると INSERT が失敗し、同期の更新も同じトランザクションで戻る。
-- 先にリリースの current を v5per-race-hold-67f7d45f… へ戻すこと。
-- 今日までの変更履歴の行も消える。
BEGIN;
SET LOCAL lock_timeout = '2s';
DROP TABLE boat_data_stage.race_deadline_changes;
COMMIT;
