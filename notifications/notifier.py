# -*- coding: utf-8 -*-
import requests
from config.settings import (
    ENABLE_LINE_NOTIFY,
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_USER_ID
)


def send_line_message(message):
    if not ENABLE_LINE_NOTIFY:
        print("📴 LINE送信スキップ")
        return {
            "ok": False,
            "skip_reason": "disabled"
        }

    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        return {
            "ok": res.ok,
            "status_code": res.status_code,
            "text": res.text
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }
