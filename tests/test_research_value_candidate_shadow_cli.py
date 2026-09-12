import json
import subprocess
import sys
from pathlib import Path


def test_cli_writes_compact_summary(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    sample = root / "tests" / "data" / "value_candidate_shadow_sample.csv"
    output = tmp_path / "summary.json"
    subprocess.run(
        [
            sys.executable,
            str(root / "research_value_candidate_shadow.py"),
            "--input",
            str(sample),
            "--output",
            str(output),
            "--stake-yen",
            "100",
            "--gates",
            "1.10",
        ],
        check=True,
        cwd=root,
    )
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["meta"]["production_write"] is False
    assert data["meta"]["purchase_action"] is False
    assert data["by_gate"]["1.10"]["overall"]["candidates"] >= 1
    assert output.stat().st_size < 100_000
