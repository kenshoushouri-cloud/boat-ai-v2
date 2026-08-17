# -*- coding: utf-8 -*-
"""
probe_k_extract_pg_v2.py

公式KファイルのLZH解凍プローブ v2。
DB更新なし。

改善点:
- lhafile が未導入なら、現在実行中のPythonに対して
  `python -m pip install lhafile==0.3.1` を一時実行してから再試行する。
- Railwayの永続環境は変更しない。コンテナ終了後は消える可能性がある。
- これで解凍可否を先に確定し、成功後にrequirements.txt側を恒久修正する。
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import requests

VERSION = "2026-08-17 k-extract-probe-v2-auto-lhafile"

TARGET_DATE = os.getenv("TARGET_DATE", "2026-08-16")
TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
AUTO_INSTALL_LHAFILE = (os.getenv("AUTO_INSTALL_LHAFILE", "1") == "1")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; boat-ai-v2/1.0; +https://boatrace.jp)"
    ),
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}


def build_url(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (
        "https://www1.mbrace.or.jp/od2/K/"
        f"{dt.strftime('%Y%m')}/k{dt.strftime('%y%m%d')}.lzh"
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


def import_lhafile():
    try:
        import lhafile  # type: ignore
        return lhafile, "already-installed"
    except ImportError:
        return None, "not-installed"


def install_lhafile():
    print("\n=== TEMPORARY PYTHON PACKAGE INSTALL ===", flush=True)
    print(f"python={sys.executable}", flush=True)
    print("package=lhafile==0.3.1", flush=True)

    cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "lhafile==0.3.1",
    ]

    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )

    # ログ過多防止のため末尾30行のみ
    lines = (p.stdout or "").splitlines()
    for line in lines[-30:]:
        print(line[:500], flush=True)

    print(f"pip_returncode={p.returncode}", flush=True)
    return p.returncode == 0


def extract_with_lhafile(archive: Path, outdir: Path):
    mod, status = import_lhafile()
    print(f"lhafile_import_before={status}", flush=True)

    if mod is None and AUTO_INSTALL_LHAFILE:
        if not install_lhafile():
            return None

        # import cache対策
        import importlib
        importlib.invalidate_caches()

        try:
            import lhafile as mod  # type: ignore
            print("lhafile_import_after=SUCCESS", flush=True)
        except Exception as exc:
            print(
                f"lhafile_import_after=ERROR "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            return None

    elif mod is None:
        return None

    try:
        lha = mod.Lhafile(str(archive))
        names = lha.namelist()
        print(f"archive_members={names}", flush=True)

        for name in names:
            data = lha.read(name)
            target = outdir / Path(name).name
            target.write_bytes(data)

        return "python-lhafile" if names else None

    except Exception as exc:
        print(
            f"lhafile_extract_error={type(exc).__name__}: {exc}",
            flush=True,
        )
        return None


def decode_text(data: bytes):
    for enc in ("cp932", "shift_jis", "utf-8", "euc_jp"):
        try:
            return enc, data.decode(enc)
        except UnicodeDecodeError:
            pass
    return "latin-1-fallback", data.decode("latin-1", errors="replace")


def main():
    print(f"✅ probe_k_extract_pg_v2.py VERSION {VERSION}", flush=True)
    print(f"TARGET_DATE={TARGET_DATE}", flush=True)
    print(f"python={sys.executable}", flush=True)
    print(f"python_version={sys.version.split()[0]}", flush=True)
    print("DB書き込みなし。", flush=True)
    print(
        "注: lhafile未導入時のpip installはこの実行コンテナ内だけの"
        "一時インストールです。",
        flush=True,
    )

    url = build_url(TARGET_DATE)
    print(f"K_URL={url}", flush=True)

    with tempfile.TemporaryDirectory(prefix="boat_k_probe_") as td:
        base = Path(td)
        archive = base / "target.lzh"
        outdir = base / "out"
        outdir.mkdir()

        download(url, archive)

        print("\n=== SYSTEM EXTRACTORS ===", flush=True)
        for cmd in ("7z", "7zz", "lha", "unar"):
            print(f"{cmd}={shutil.which(cmd) or 'NOT_FOUND'}", flush=True)

        print("\n=== PYTHON LZH EXTRACT ===", flush=True)
        method = extract_with_lhafile(archive, outdir)

        if not method:
            print("RESULT=EXTRACT_FAILED", flush=True)
            return

        print(f"EXTRACT_METHOD={method}", flush=True)

        files = sorted(x for x in outdir.rglob("*") if x.is_file())
        print("\n=== EXTRACTED FILES ===", flush=True)
        for x in files[:10]:
            print(f"name={x.name} bytes={x.stat().st_size}", flush=True)

        if not files:
            print("RESULT=NO_EXTRACTED_FILES", flush=True)
            return

        target = max(files, key=lambda x: x.stat().st_size)
        data = target.read_bytes()
        enc, text = decode_text(data)
        lines = text.splitlines()

        print("\n=== TEXT INFO ===", flush=True)
        print(f"selected={target.name}", flush=True)
        print(f"bytes={len(data)}", flush=True)
        print(f"encoding={enc}", flush=True)
        print(f"line_count={len(lines)}", flush=True)

        print("\n=== FIRST 100 LINES ===", flush=True)
        for i, line in enumerate(lines[:100], 1):
            print(f"{i:03d}: {line[:350]}", flush=True)

        print("\nRESULT=SUCCESS", flush=True)


if __name__ == "__main__":
    main()