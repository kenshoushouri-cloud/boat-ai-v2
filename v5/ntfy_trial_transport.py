# -*- coding: utf-8 -*-
"""ConoHa local ntfy publisher for V5 trial messages.

Defaults to DRY_RUN. No model decision, database, betting, or LINE access.
No remote/public ntfy URL is configurable: publish only to the local server.
The sender is a write-only user. Do not provide passwords as CLI arguments.
Real sends require BOTH --send and V5_NTFY_SEND=YES, plus the password in
V5_NTFY_PUBLISHER_PASSWORD (e.g. a protected systemd EnvironmentFile).
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from collections.abc import Callable
from typing import Any
from urllib import error, request

URL = "http://127.0.0.1:2586/v5-race-alerts"
USERNAME = "v5-publisher"
MAX_TEXT_CHARS = 3500
MAX_TITLE_CHARS = 100


def validate_message(message: str, title: str) -> tuple[str, str]:
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= MAX_TEXT_CHARS:
        raise ValueError("message must be 1..3500 characters")
    if not isinstance(title, str) or not 1 <= len(title) <= MAX_TITLE_CHARS:
        raise ValueError("title must be 1..100 characters")
    # Keep headers strictly ASCII and prevent header injection. Japanese text
    # is supported in the body, which is always sent as UTF-8.
    if not title.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in title):
        raise ValueError("title must be printable ASCII without newlines")
    return message.strip(), title


def publish(
    message: str,
    *,
    title: str = "V5 Trial Notice",
    allow_send: bool = False,
    environ: dict[str, str] | None = None,
    http_open: Callable[..., Any] | None = None,
) -> str:
    """Return DRY_RUN or SENT; never output credentials or request URLs."""
    message, title = validate_message(message, title)
    if not allow_send:
        return "DRY_RUN"
    env = os.environ if environ is None else environ
    if env.get("V5_NTFY_SEND") != "YES":
        raise ValueError("V5_NTFY_SEND=YES required for a real send")
    password = env.get("V5_NTFY_PUBLISHER_PASSWORD", "")
    if not password:
        raise ValueError("publisher credential is not configured")
    auth = base64.b64encode(f"{USERNAME}:{password}".encode("utf-8")).decode("ascii")
    req = request.Request(
        URL,
        data=message.encode("utf-8"),
        headers={
            "Authorization": f"Basic {auth}",
            "Title": title,
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    open_fn = request.urlopen if http_open is None else http_open
    try:
        with open_fn(req, timeout=15) as response:
            status = response.status
    except error.HTTPError as exc:
        # Deliberately do not include response text or exception repr:
        # they may contain credentials or server details.
        raise RuntimeError(f"NTFY_HTTP_ERROR_{exc.code}") from None
    except (error.URLError, TimeoutError, OSError):
        raise RuntimeError("NTFY_NETWORK_ERROR") from None
    if status not in (200, 201, 202):
        raise RuntimeError(f"NTFY_HTTP_ERROR_{status}")
    return "SENT"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="message content")
    src.add_argument("--stdin", action="store_true", help="read UTF-8 message on stdin")
    parser.add_argument("--title", default="V5 Trial Notice", help="ASCII title")
    parser.add_argument("--send", action="store_true", help="allow a single actual send")
    args = parser.parse_args(argv)
    message = sys.stdin.read(MAX_TEXT_CHARS + 1) if args.stdin else args.text
    try:
        result = publish(message, title=args.title, allow_send=args.send)
    except (ValueError, RuntimeError) as exc:
        print(f"V5_NTFY_STATUS=ERROR reason={exc}", file=sys.stderr)
        return 2
    print(f"V5_NTFY_STATUS={result} chars={len(message.strip())}")
    if result == "DRY_RUN":
        print(message.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
