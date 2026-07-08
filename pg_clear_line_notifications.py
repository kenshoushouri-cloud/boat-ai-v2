# -*- coding: utf-8 -*-
"""
pg_clear_line_notifications.py

Railway Postgres 本番前のLINE通知ログ削除用。
テスト送信ログで DAILY_LINE_LIMIT や重複判定に影響が出ないようにします。

Railway Start Command:
    python -u pg_clear_line_notifications.py

Variables:
    DATABASE_URL=${{postgres.DATABASE_URL}}
    PG_CLEAR_LINE_CONFIRM=YES

注意:
    v2_line_notifications のみ削除します。
    レース、出走表、結果、オッズ、直前判定データは削除しません。
"""

from __future__ import annotations

import os
from db_pg import fetch_one, execute


def main() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")

    confirm = os.getenv("PG_CLEAR_LINE_CONFIRM", "")
    if confirm != "YES":
        print("PG_CLEAR_LINE_CONFIRM=YES が必要です。削除せず終了します。", flush=True)
        return

    before = fetch_one("select count(*) as cnt from v2_line_notifications;")
    before_cnt = int(before.get("cnt") or 0)

    execute("delete from v2_line_notifications;")

    after = fetch_one("select count(*) as cnt from v2_line_notifications;")
    after_cnt = int(after.get("cnt") or 0)

    print("=== clear line notifications finished ===", flush=True)
    print(f"before: {before_cnt}", flush=True)
    print(f"after: {after_cnt}", flush=True)


if __name__ == "__main__":
    main()