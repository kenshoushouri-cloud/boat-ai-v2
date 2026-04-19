# -*- coding: utf-8 -*-
import requests
from config.settings import LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID


def send_line_message(message):
    url = "https://api.line.me/v2/bot/message/push"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN.strip()}"
    }

    payload = {
        "to": LINE_USER_ID.strip(),
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)

        status_code = res.status_code
        text = res.text

        if status_code == 429:
            return {
                "ok": False,
                "status_code": status_code,
                "text": text,
                "skip_reason": "LINE月間上限"
            }

        return {
            "ok": (200 <= status_code < 300),
            "status_code": status_code,
            "text": text,
            "skip_reason": None
        }

    except Exception as e:
        return {
            "ok": False,
            "status_code": 0,
            "text": repr(e),
            "skip_reason": "LINE送信例外"
        }
