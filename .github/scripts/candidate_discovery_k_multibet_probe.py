# -*- coding: utf-8 -*-
"""Read-only official K archive probe for multi-bet payouts.

Downloads one historical official K archive and checks whether venue/race context
can be associated with trifecta, trio, and exacta payout lines. This module is
fully standalone: no database module, external service connector, message send,
purchase action, or persistence.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import lhafile  # type: ignore
import requests

TARGET_DATE = os.getenv("CANDIDATE_K_PROBE_DATE", "2026-08-12")
OUTPUT = Path(os.getenv("CANDIDATE_K_PROBE_OUTPUT", "candidate-discovery-k-multibet-probe.json"))
TIMEOUT = int(os.getenv("CANDIDATE_K_HTTP_TIMEOUT", "30"))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; boat-ai-v2/1.0; +https://boatrace.jp)",
    "Accept-Language": "ja,en-US;q=0.8,en;q=0.6",
}
BET_LABELS = {
    "３連単": "trifecta",
    "3連単": "trifecta",
    "３連複": "trio",
    "3連複": "trio",
    "２連単": "exacta",
    "2連単": "exacta",
}
PAYOUT_RE = re.compile(
    r"(?P<label>[２３23]連[単複])\s+"
    r"(?P<ticket>[1-6](?:-[1-6]){1,2})\s+"
    r"(?P<payout>[\d,]+)"
)
MARKER_RE = re.compile(r"^(?P<venue>\d{2})K(?P<kind>BGN|END)\b")
HEADER_RE = re.compile(r"^(?P<race>\d{1,2})R\s+.+?\s+H\d+m\b")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def k_url(date_str: str) -> str:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"https://www1.mbrace.or.jp/od2/K/{dt:%Y%m}/k{dt:%y%m%d}.lzh"


def get_k_text(date_str: str) -> str:
    url = k_url(date_str)
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    print(f"CANDIDATE_K_PROBE_GET=status:{response.status_code} bytes:{len(response.content)}", flush=True)
    response.raise_for_status()
    with tempfile.TemporaryDirectory(prefix="candidate_k_probe_") as td:
        archive = Path(td) / "k.lzh"
        archive.write_bytes(response.content)
        lha = lhafile.Lhafile(str(archive))
        names = lha.namelist()
        if not names:
            raise RuntimeError("K archive has no members")
        raw = lha.read(names[0])
    return raw.decode("cp932")


def main() -> None:
    print("CANDIDATE_K_PROBE_MODE=official_archive_read_only", flush=True)
    print(f"CANDIDATE_K_PROBE_DATE={TARGET_DATE}", flush=True)
    print("CANDIDATE_K_PROBE_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    text = get_k_text(TARGET_DATE)
    lines = text.splitlines()
    markers = []
    payouts = []
    counts: Counter[str] = Counter()
    current_venue = None
    current_race = None

    for idx, raw in enumerate(lines):
        s = clean(raw)
        marker = MARKER_RE.fullmatch(s)
        if marker:
            venue = marker.group("venue")
            kind = marker.group("kind")
            markers.append({"line": idx + 1, "venue": venue, "kind": kind})
            if kind == "BGN":
                current_venue = venue
                current_race = None
            else:
                current_venue = None
                current_race = None
            continue

        header = HEADER_RE.match(s)
        if header:
            current_race = int(header.group("race"))

        m = PAYOUT_RE.search(s)
        if not m:
            continue
        bet_type = BET_LABELS.get(m.group("label"))
        if bet_type not in {"trifecta", "trio", "exacta"}:
            continue
        ticket = m.group("ticket")
        payout = int(m.group("payout").replace(",", ""))
        counts[bet_type] += 1
        payouts.append({
            "line": idx + 1,
            "venue": current_venue,
            "race_no": current_race,
            "bet_type": bet_type,
            "ticket": ticket,
            "payout_yen": payout,
            "source": s,
        })

    mapped = [x for x in payouts if x["venue"] and x["race_no"]]
    mapped_counts = Counter(x["bet_type"] for x in mapped)
    summary = {
        "contract": "candidate_discovery_k_multibet_probe_v2_standalone",
        "date": TARGET_DATE,
        "source_url": k_url(TARGET_DATE),
        "line_count": len(lines),
        "marker_count": len(markers),
        "markers_sample": markers[:20],
        "payout_counts": dict(sorted(counts.items())),
        "mapped_payout_counts": dict(sorted(mapped_counts.items())),
        "payout_rows": len(payouts),
        "mapped_payout_rows": len(mapped),
        "payout_sample": payouts[:30],
        "all_three_bet_types_present": all(counts[x] > 0 for x in ("trifecta", "trio", "exacta")),
        "all_three_bet_types_mapped": all(mapped_counts[x] > 0 for x in ("trifecta", "trio", "exacta")),
        "venue_race_mapping_observed": bool(mapped),
        "mutation_performed": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"CANDIDATE_K_PROBE_COUNTS={json.dumps(dict(sorted(counts.items())), sort_keys=True)}", flush=True)
    print(f"CANDIDATE_K_PROBE_MAPPED_COUNTS={json.dumps(dict(sorted(mapped_counts.items())), sort_keys=True)}", flush=True)
    print(f"CANDIDATE_K_PROBE_MARKERS={len(markers)} MAPPED_PAYOUT_ROWS={len(mapped)}", flush=True)
    print(f"CANDIDATE_K_PROBE_SAMPLE={json.dumps(payouts[:8], ensure_ascii=False, sort_keys=True)}", flush=True)
    if not summary["all_three_bet_types_present"]:
        raise RuntimeError("not all target bet types were found in official K archive")
    if not summary["all_three_bet_types_mapped"]:
        raise RuntimeError("target payout types were found but venue/race mapping is incomplete")
    print("CANDIDATE_K_PROBE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
