# -*- coding: utf-8 -*-
"""
probe_k_extract_pg.py

2026-08-16等の公式Kファイルを取得し、
Railway環境で利用可能な方法だけを使ってLZH解凍を試す。

DB更新なし。
解凍成功後はTXTの
- ファイル名
- バイト数
- 推定文字コード
- 先頭80行
- 行数
だけを表示する。

大量ログ回避のため出力上限あり。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import requests

VERSION = "2026-08-17 k-extract-probe-v1"

TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-16")
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
    ),
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}


def build_url(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    yyyymm = dt.strftime("%Y%m")
    yymmdd = dt.strftime("%y%m%d")
    return (
        f"https://www1.mbrace.or.jp/"
        f"od2/K/{yyyymm}/k{yymmdd}.lzh"
    )


def download(url: str, path: Path) -> None:
    r = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    print(
        f"download status={r.status_code} bytes={len(r.content)} "
        f"ctype={r.headers.get('Content-Type')}",
        flush=True,
    )
    r.raise_for_status()
    path.write_bytes(r.content)


def try_command_extract(archive: Path, outdir: Path):
    methods = []

    # 7z / 7zz
    for cmd in ("7z", "7zz"):
        exe = shutil.which(cmd)
        if exe:
            methods.append(
                (
                    cmd,
                    [exe, "x", "-y", f"-o{outdir}", str(archive)],
                )
            )

    # lha
    exe = shutil.which("lha")
    if exe:
        methods.append(
            (
                "lha",
                [exe, "x", "-w=" + str(outdir), str(archive)],
            )
        )

    # unar
    exe = shutil.which("unar")
    if exe:
        methods.append(
            (
                "unar",
                [exe, "-o", str(outdir), str(archive)],
            )
        )

    if not methods:
        return None, []

    attempts = []

    for name, args in methods:
        try:
            p = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=60,
            )
            msg = (p.stdout or "").strip()
            attempts.append(
                f"{name}: rc={p.returncode} out={msg[:500]!r}"
            )

            files = [
                x for x in outdir.rglob("*")
                if x.is_file()
            ]
            if p.returncode == 0 and files:
                return name, attempts

        except Exception as exc:
            attempts.append(
                f"{name}: ERROR={type(exc).__name__}: {exc}"
            )

    return None, attempts


def try_python_extract(archive: Path, outdir: Path):
    attempts = []

    # lhafile
    try:
        import lhafile  # type: ignore

        attempts.append("python lhafile: INSTALLED")

        lha = lhafile.Lhafile(str(archive))
        names = lha.namelist()

        for name in names:
            data = lha.read(name)
            target = outdir / Path(name).name
            target.write_bytes(data)

        if names:
            return "python-lhafile", attempts

    except ImportError:
        attempts.append("python lhafile: NOT_INSTALLED")
    except Exception as exc:
        attempts.append(
            f"python lhafile: ERROR={type(exc).__name__}: {exc}"
        )

    return None, attempts


def detect_decode(data: bytes):
    encodings = (
        "cp932",
        "shift_jis",
        "utf-8",
        "euc_jp",
    )

    for enc in encodings:
        try:
            text = data.decode(enc)
            return enc, text
        except UnicodeDecodeError:
            pass

    return "latin-1-fallback", data.decode("latin-1", errors="replace")


def main():
    print(
        f"✅ probe_k_extract_pg.py VERSION {VERSION}",
        flush=True,
    )
    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print("DB書き込みなし。", flush=True)

    url = build_url(TARGET_DATE)
    print(f"K_URL={url}", flush=True)

    with tempfile.TemporaryDirectory(
        prefix="boat_k_probe_"
    ) as tmp:
        tmpdir = Path(tmp)
        archive = tmpdir / "target.lzh"
        outdir = tmpdir / "out"
        outdir.mkdir()

        download(url, archive)

        print("\n=== EXTRACTOR AVAILABILITY ===", flush=True)
        for cmd in ("7z", "7zz", "lha", "unar"):
            print(
                f"{cmd}={shutil.which(cmd) or 'NOT_FOUND'}",
                flush=True,
            )

        method, attempts = try_command_extract(
            archive,
            outdir,
        )

        if method is None:
            py_method, py_attempts = try_python_extract(
                archive,
                outdir,
            )
            attempts.extend(py_attempts)
            method = py_method

        print("\n=== EXTRACT ATTEMPTS ===", flush=True)
        for line in attempts[:20]:
            print(line, flush=True)

        if method is None:
            print("\nRESULT=NO_EXTRACTOR", flush=True)
            print(
                "NEXT_HINT=Railway環境に7z/7zz/lha/unarが無い場合は、"
                "Python依存だけで解凍する方法を追加します。",
                flush=True,
            )
            return

        print(f"\nEXTRACT_METHOD={method}", flush=True)

        files = sorted(
            x for x in outdir.rglob("*")
            if x.is_file()
        )

        print("\n=== EXTRACTED FILES ===", flush=True)
        for x in files[:20]:
            print(
                f"name={x.name} bytes={x.stat().st_size}",
                flush=True,
            )

        if not files:
            print("RESULT=EXTRACTED_BUT_NO_FILES", flush=True)
            return

        # 最大ファイルを本文候補とする。
        target = max(files, key=lambda x: x.stat().st_size)
        data = target.read_bytes()

        enc, text = detect_decode(data)

        print("\n=== TEXT INFO ===", flush=True)
        print(f"selected={target.name}", flush=True)
        print(f"bytes={len(data)}", flush=True)
        print(f"encoding={enc}", flush=True)

        lines = text.splitlines()
        print(f"line_count={len(lines)}", flush=True)

        print("\n=== FIRST 80 LINES ===", flush=True)
        for i, line in enumerate(lines[:80], 1):
            # rate limit対策
            safe = line[:300]
            print(
                f"{i:03d}: {safe}",
                flush=True,
            )

        print("\nRESULT=SUCCESS", flush=True)


if __name__ == "__main__":
    main()