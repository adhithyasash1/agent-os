from agentos.eval.scorer import score_answer, score_expected


def test_score_expected_all_present():
    assert score_expected("Paris is the capital.", {"expected_contains": ["Paris"]}) == 1.0


def test_score_expected_partial():
    s = score_expected("Lists are mutable.",
                       {"expected_contains": ["mutable", "immutable"]})
    assert s == 0.5


def test_score_expected_missing():
    assert score_expected("Nope.", {"expected_contains": ["Paris"]}) == 0.0


def test_score_expected_no_expectation_returns_none():
    assert score_expected("anything", None) is None


def test_heuristic_empty():
    assert score_answer("q", "", "") == 0.0


def test_heuristic_refusal():
    s = score_answer("q", "I don't know.", "")
    assert 0.0 < s <= 0.4


def test_heuristic_baseline_nonempty():
    s = score_answer("q", "This is a real answer with several sentences and substance.", "")
    assert s >= 0.5


def test_heuristic_grounded_bonus():
    ctx = "Paris capital France Seine tower Eiffel"
    ungrounded = score_answer("q", "Totally unrelated banana chips.", ctx)
    grounded = score_answer("q", "Paris is the capital of France, home to the Eiffel tower.", ctx)
    assert grounded > ungrounded
