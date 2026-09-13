# -*- coding: utf-8 -*-
"""Read-only official K archive probe for multi-bet payouts.

Downloads one historical official K archive and checks whether venue/race context
can be associated with trifecta, trio, and exacta payout lines. No database use,
no persistence outside the CI artifact, no Production/LINE/BUY action.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SOURCE = REPO_ROOT / "probe_k_parse_compare_pg_v3.py"
spec = importlib.util.spec_from_file_location("probe_k_parse_compare_pg_v3", SOURCE)
k = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(k)

TARGET_DATE = os.getenv("CANDIDATE_K_PROBE_DATE", "2026-08-12")
OUTPUT = Path(os.getenv("CANDIDATE_K_PROBE_OUTPUT", "candidate-discovery-k-multibet-probe.json"))
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


def main() -> None:
    print("CANDIDATE_K_PROBE_MODE=official_archive_read_only", flush=True)
    print(f"CANDIDATE_K_PROBE_DATE={TARGET_DATE}", flush=True)
    print("CANDIDATE_K_PROBE_DB_WRITE=0 LINE=0 BUY=0 PROD_CHANGE=0", flush=True)

    text = k.get_k_text(TARGET_DATE)
    lines = text.splitlines()
    markers = []
    payouts = []
    counts: Counter[str] = Counter()
    current_venue = None
    current_race = None

    for idx, raw in enumerate(lines):
        s = k.clean(raw)
        marker = MARKER_RE.fullmatch(s)
        if marker:
            current_venue = marker.group("venue") if marker.group("kind") == "BGN" else current_venue
            markers.append({"line": idx + 1, "venue": marker.group("venue"), "kind": marker.group("kind")})
            if marker.group("kind") == "END":
                current_venue = None
                current_race = None
            continue

        header = k.parse_header(raw)
        if header:
            current_race = int(header["race_no"])

        m = PAYOUT_RE.search(s)
        if not m:
            continue
        label = m.group("label")
        bet_type = BET_LABELS.get(label)
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
    summary = {
        "contract": "candidate_discovery_k_multibet_probe_v1",
        "date": TARGET_DATE,
        "line_count": len(lines),
        "marker_count": len(markers),
        "markers_sample": markers[:20],
        "payout_counts": dict(sorted(counts.items())),
        "payout_rows": len(payouts),
        "mapped_payout_rows": len(mapped),
        "payout_sample": payouts[:30],
        "all_three_bet_types_present": all(counts[x] > 0 for x in ("trifecta", "trio", "exacta")),
        "venue_race_mapping_observed": bool(mapped),
        "mutation_performed": False,
        "production_behavior_changed": False,
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"CANDIDATE_K_PROBE_COUNTS={json.dumps(dict(sorted(counts.items())), sort_keys=True)}", flush=True)
    print(f"CANDIDATE_K_PROBE_MARKERS={len(markers)} MAPPED_PAYOUT_ROWS={len(mapped)}", flush=True)
    print(f"CANDIDATE_K_PROBE_SAMPLE={json.dumps(payouts[:8], ensure_ascii=False, sort_keys=True)}", flush=True)
    if not summary["all_three_bet_types_present"]:
        raise RuntimeError("not all target bet types were found in official K archive")
    print("CANDIDATE_K_PROBE_RESULT=PASS_READ_ONLY", flush=True)


if __name__ == "__main__":
    main()
