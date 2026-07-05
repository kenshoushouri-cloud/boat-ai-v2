# -*- coding: utf-8 -*-
"""
pg_clear_line_notifications.py

Railway Postgres版。
指定日の v2_line_notifications を削除します。
DRY_RUNテスト時に保存された通知履歴を消したい時だけ使います。

Railway Start Command:
    python pg_clear_line_notifications.py

Variables:
    DATABASE_URL
    TARGET_DATE=YYYY-MM-DD
    PG_CLEAR_CONFIRM=YES
"""

import os
from datetime import datetime, timedelta, timezone

from db_pg import execute, fetch_one

JST = timezone(timedelta(hours=9))
TARGET_DATE = os.getenv("TARGET_DATE") or datetime.now(JST).strftime("%Y-%m-%d")


def main():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL が必要です。")
    if os.getenv("PG_CLEAR_CONFIRM") != "YES":
        raise RuntimeError("安全装置: PG_CLEAR_CONFIRM=YES を設定してから実行してください。")

    before = fetch_one(
        "select count(*) as c from v2_line_notifications where race_date = %s;",
        (TARGET_DATE,),
    )
    before_count = int(before.get("c", 0)) if before else 0

    execute(
        "delete from v2_line_notifications where race_date = %s;",
        (TARGET_DATE,),
    )

    after = fetch_one(
        "select count(*) as c from v2_line_notifications where race_date = %s;",
        (TARGET_DATE,),
    )
    after_count = int(after.get("c", 0)) if after else 0

    print("=== clear line notifications ===", flush=True)
    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print(f"before={before_count}", flush=True)
    print(f"after={after_count}", flush=True)
    print("=== clear finished ===", flush=True)


if __name__ == "__main__":
    main()