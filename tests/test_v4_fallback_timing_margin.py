from research.v4_fallback_timing_margin import evaluate


def test_only_0820_passes_frozen_safety_criteria():
    r = evaluate()
    passing = [x["candidate_jst"] for x in r["candidates"] if x["passes_all"]]
    assert passing == ["08:20"]
    assert r["preferred_candidate_for_separate_approval"] == "08:20"


def test_current_0825_has_sub_five_minute_worst_margin():
    r = evaluate()
    current = next(x for x in r["candidates"] if x["candidate_jst"] == "08:25")
    assert current["projected_worst_feed_headroom_seconds"] < 300


def test_0820_has_more_than_six_minute_worst_margin():
    r = evaluate()
    x = next(x for x in r["candidates"] if x["candidate_jst"] == "08:20")
    assert x["projected_worst_feed_headroom_seconds"] > 360


def test_0818_fails_spacing_even_though_margin_is_larger():
    r = evaluate()
    x = next(x for x in r["candidates"] if x["candidate_jst"] == "08:18")
    assert x["checks"]["after_cutoff_ge_5m"] is False
    assert x["checks"]["after_primary_nominal_ge_4m"] is False
    assert x["passes_all"] is False


def test_no_mutation_is_claimed():
    r = evaluate()
    assert r["railway_change_performed"] is False
    assert r["production_change_performed"] is False
