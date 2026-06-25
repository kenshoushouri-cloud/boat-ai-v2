# -*- coding: utf-8 -*-
"""
line_test_push.py

LINE Messaging API の接続確認用。
買い目判定とは無関係に、固定テストメッセージを1通だけ送信します。

Railway Start Command:
    python line_test_push.py
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import requests

JST = timezone(timedelta(hours=9))

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_TO = (
    os.getenv("LINE_TO")
    or os.getenv("LINE_USER_ID")
    or os.getenv("LINE_GROUP_ID")
    or ""
).strip()

DRY_RUN = os.getenv("DRY_RUN", "0").strip() in ("1", "true", "True", "yes", "YES")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "35"))

def main() -> None:
    print("✅ line_test_push.py VERSION 2026-06-25 line-test", flush=True)
    print(f"DRY_RUN={DRY_RUN}", flush=True)

    message = (
        "【競艇AI テスト通知】\n"
        "LINE接続確認です。\n"
        "これは購入しないテスト通知です。\n"
        f"送信時刻: {datetime.now(JST).strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print("--- message ---", flush=True)
    print(message, flush=True)

    if DRY_RUN:
        print("DRY_RUN=1 のためLINE送信は行いません。", flush=True)
        print("=== LINEテスト終了 ===", flush=True)
        return

    if not LINE_CHANNEL_ACCESS_TOKEN:
        raise RuntimeError("LINE_CHANNEL_ACCESS_TOKEN が未設定です。")
    if not LINE_TO:
        raise RuntimeError("LINE_TO / LINE_USER_ID / LINE_GROUP_ID のいずれかが未設定です。")

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "to": LINE_TO,
        "messages": [{"type": "text", "text": message}],
    }

    r = requests.post(
        url,
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False),
        timeout=HTTP_TIMEOUT,
    )

    print(f"LINE response status={r.status_code}", flush=True)
    print(f"LINE response body={r.text[:1000]}", flush=True)

    if 200 <= r.status_code < 300:
        print("✅ LINEテスト送信成功", flush=True)
    else:
        print("❌ LINEテスト送信失敗", flush=True)

    print("=== LINEテスト終了 ===", flush=True)

if __name__ == "__main__":
    main()