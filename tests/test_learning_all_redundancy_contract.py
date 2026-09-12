from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_production_final_chain_defaults_to_final_ab():
    run_final = text("run_final_pg.py")
    pipeline = text("v25_final_realtime_pipeline_pg.py")
    decision = text("v22_realtime_decision_engine_pg.py")
    exhibition = text("v22_exhibition_shadow_pg.py")
    notifier = text("v23_line_notifier_batch_pg.py")

    assert 'os.environ.setdefault("SNAPSHOT_LABEL", "final_ab")' in run_final
    assert 'os.environ.setdefault("DECISION_LABEL", "final_ab")' in run_final
    assert 'os.getenv("SNAPSHOT_LABEL", "final_ab")' in pipeline
    assert 'os.getenv("SNAPSHOT_LABEL", "final_ab")' in decision
    assert 'os.getenv("SNAPSHOT_LABEL", "final_ab")' in exhibition
    assert 'os.getenv("SNAPSHOT_LABEL", "final_ab")' in notifier

    for body in (run_final, pipeline, decision, exhibition, notifier):
        assert "learning_all" not in body


def test_nightly_chain_defaults_to_final_ab_and_not_learning_all():
    nightly = text("run_nightly_results_pg.py")
    assert '"SNAPSHOT_LABEL": os.getenv("SNAPSHOT_LABEL", "final_ab")' in nightly
    assert "learning_all" not in nightly


def test_learning_wrapper_is_collection_only_and_isolated():
    learning = text("run_learning_all_realtime_pg.py")
    assert 'env["COLLECT_SCOPE"] = "all"' in learning
    assert 'os.getenv("LEARNING_SNAPSHOT_LABEL", "learning_all")' in learning
    assert '"/tmp/v21_learning_all_target_race_ids.txt"' in learning
    assert 'collector = base_dir / "v21_realtime_collector_pg_safe.py"' in learning
    assert "LINE通知なし" in learning
    assert "本番判定なし" in learning
    assert "購入処理なし" in learning

    forbidden = (
        "v22_realtime_decision_engine_pg.py",
        "run_v22_targeted_pg.py",
        "v23_line_notifier_batch_pg.py",
        "send_line",
        "line_push",
        "purchase_action",
    )
    lower = learning.lower()
    for token in forbidden:
        assert token.lower() not in lower


def test_final_pipeline_routes_same_final_label_to_collection_and_decision():
    pipeline = text("v25_final_realtime_pipeline_pg.py")
    assert '"SNAPSHOT_LABEL": SNAPSHOT_LABEL' in pipeline
    assert '[sys.executable, "v21_realtime_collector_pg_safe.py"]' in pipeline
    assert '[sys.executable, "run_v22_targeted_pg.py"]' in pipeline
    assert '[sys.executable, "v22_exhibition_shadow_pg.py"]' in pipeline
    assert '[sys.executable, "v23_line_notifier_batch_pg.py"]' in pipeline


def test_targeted_decision_passes_requested_snapshot_label_through():
    targeted = text("run_v22_targeted_pg.py")
    assert "def _rt(date_str: str, snapshot_label: str):" in targeted
    assert "_original_rt(date_str, snapshot_label)" in targeted
    assert "learning_all" not in targeted


def test_no_other_top_level_runtime_hard_codes_learning_all():
    """Keep the learning label producer-only among top-level runtime scripts.

    Research/CI audits under subdirectories may mention the literal label, but a
    new top-level executable must not silently become dependent on it.
    """
    hits = []
    for path in sorted(ROOT.glob("*.py")):
        if "learning_all" in path.read_text(encoding="utf-8").lower():
            hits.append(path.name)
    assert hits == ["run_learning_all_realtime_pg.py"]
