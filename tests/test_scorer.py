from agentos.eval.scorer import llm_judge, score_answer, score_answer_details, score_expected


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


def test_heuristic_is_not_trustworthy():
    details = score_answer_details("q", "Some plausible answer.", "")
    assert details["mode"] == "heuristic"
    assert details["trustworthy"] is False


def test_heuristic_caps_at_0_6():
    """Without ground-truth evidence the heuristic must not exceed 0.6."""
    ctx = "Paris capital France Seine tower Eiffel"
    details = score_answer_details(
        "q",
        "Paris Paris Paris France Eiffel tower capital Seine.",
        ctx,
    )
    assert details["score"] <= 0.6


def test_heuristic_grounded_bonus():
    ctx = "Paris capital France Seine tower Eiffel"
    ungrounded = score_answer("q", "Totally unrelated banana chips.", ctx)
    grounded = score_answer("q", "Paris is the capital of France, home to the Eiffel tower.", ctx)
    assert grounded > ungrounded


def test_expected_is_trustworthy():
    details = score_answer_details(
        "q", "Paris is the capital.", "", expected={"expected_contains": ["Paris"]}
    )
    assert details["trustworthy"] is True
    assert details["mode"] == "expected"


class _StubLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[tuple[str, str | None]] = []

    async def complete(self, prompt: str, system: str | None = None) -> str:
        self.calls.append((prompt, system))
        return self.response


async def test_llm_judge_trusts_high_scores():
    llm = _StubLLM('{"correct": 0.95, "grounded": 0.9, "reason": "matches"}')
    details = await llm_judge(llm, "q", "Paris.", "Paris capital France")
    assert details["mode"] == "llm-judge"
    assert details["trustworthy"] is True
    assert details["score"] > 0.8


async def test_llm_judge_distrusts_partial():
    llm = _StubLLM('{"correct": 0.5, "grounded": 0.2, "reason": "thin"}')
    details = await llm_judge(llm, "q", "Maybe.", "")
    assert details["trustworthy"] is False


async def test_llm_judge_falls_back_on_bad_json():
    llm = _StubLLM("not json at all")
    details = await llm_judge(llm, "q", "Some answer.", "")
    assert details["mode"] == "heuristic"
    assert details["trustworthy"] is False
    assert "judge_error" in details


async def test_llm_judge_falls_back_on_exception():
    class _BoomLLM:
        async def complete(self, prompt, system=None):
            raise RuntimeError("upstream down")

    details = await llm_judge(_BoomLLM(), "q", "Some answer.", "")
    assert details["trustworthy"] is False
    assert "judge_error" in details
