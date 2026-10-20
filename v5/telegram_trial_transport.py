# -*- coding: utf-8 -*-
"""V5 Telegram trial transport. Disabled by default. No DB, betting, or LINE.

Usage (read-only preview):
  python -m v5.telegram_trial_transport --text 'V5試験通知'
To send exactly one message (requires separately stored ConoHa env):
  V5_TELEGRAM_SEND=YES TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... \
    python -m v5.telegram_trial_transport --text 'V5試験通知' --send
Do not paste token to chat or commit secrets. Bot credentials are never logged.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable
from typing import Any

API_ROOT = "https://api.telegram.org"
MAX_TEXT_CHARS = 3900
MAX_RETRY_AFTER_SEC = 30


def validate_message(message: str) -> str:
    if not isinstance(message, str):
        raise ValueError("message must be text")
    message = message.strip()
    if not 1 <= len(message) <= MAX_TEXT_CHARS:
        raise ValueError("message must be 1..3900 chars")
    return message


def get_retry_after(data: Any) -> int:
    if not isinstance(data, dict):
        return 0
    params = data.get("parameters", {})
    if not isinstance(params, dict):
        return 0
    retry = params.get("retry_after", 0)
    if type(retry) is not int or not 1 <= retry <= MAX_RETRY_AFTER_SEC:
        return 0
    return retry


def send_message(
    message: str, *,
    allow_send: bool = False,
    environ: dict[str, str] | None = None,
    http_post: Callable[..., Any] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Return DRY_RUN/SENT. Never print token, URL or chat_id."""
    message = validate_message(message)
    env = os.environ if environ is None else environ
    if not allow_send:
        return "DRY_RUN"
    if env.get("V5_TELEGRAM_SEND", "") != "YES":
        raise ValueError("send is disabled unless V5_TELEGRAM_SEND=YES")
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = env.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
    if http_post is None:
        import requests
        http_post = requests.post
    url = f"{API_ROOT}/bot{token}/sendMessage"
    params = {"chat_id": chat_id, "text": message, "disable_notification": False}
    for attempt in range(2):
        try:
            response = http_post(url, json=params, timeout=(5, 20))
        except Exception as exc:
            # Underlying libraries sometimes include URLs with token in errors.
            raise RuntimeError("TELEGRAM_NETWORK_ERROR") from None
        if response.status_code == 429 and attempt == 0:
            try:
                wait = get_retry_after(response.json())
            except Exception:
                wait = 0
            if wait:
                sleep(wait)
                continue
        if response.status_code != 200:
            raise RuntimeError(f"TELEGRAM_HTTP_ERROR_{response.status_code}")
        try:
            success = response.json().get("ok") is True
        except Exception:
            success = False
        if not success:
            raise RuntimeError("TELEGRAM_API_REJECTED")
        return "SENT"
    raise RuntimeError("TELEGRAM_RATE_LIMITED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inp = parser.add_mutually_exclusive_group(required=True)
    inp.add_argument("--text", help="single test message")
    inp.add_argument("--stdin", action="store_true", help="read report body from standard input")
    parser.add_argument("--send", action="store_true", help="actually send exactly one Telegram message")
    args = parser.parse_args(argv)
    message = sys.stdin.read(MAX_TEXT_CHARS + 1) if args.stdin else args.text
    try:
        status = send_message(message, allow_send=args.send)
    except (ValueError, RuntimeError) as exc:
        print(f"V5_TELEGRAM_STATUS=ERROR reason={exc}", file=sys.stderr, flush=True)
        return 2
    print(f"V5_TELEGRAM_STATUS={status} chars={len(message.strip())}", flush=True)
    if not args.send:
        print(message.strip(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
