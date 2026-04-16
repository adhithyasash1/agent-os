import pytest

from agentos.memory.store import MEMORY_KINDS


def test_add_and_count(memory):
    assert memory.count() == 0
    memory.add("The capital of France is Paris.", meta={"source": "test"})
    memory.add("Binary search runs in O(log n).", kind="semantic")
    assert memory.count() == 2


def test_search_returns_match(memory):
    memory.add("The capital of France is Paris.", kind="semantic")
    memory.add("The Eiffel Tower is in Paris.", kind="episodic")
    memory.add("Unrelated sentence about bananas.", kind="working")
    hits = memory.search("Paris", k=5)
    assert len(hits) >= 2
    assert all("paris" in h["text"].lower() for h in hits[:2])


def test_search_empty_query(memory):
    memory.add("anything")
    assert memory.search("", k=3) == []


def test_meta_roundtrip(memory):
    memory.add("hello", meta={"tag": "greeting", "n": 1}, kind="working")
    hits = memory.search("hello", k=1)
    assert hits[0]["meta"] == {"tag": "greeting", "n": 1}


def test_search_can_filter_by_kind(memory):
    memory.add("Paris is stored in working memory.", kind="working")
    memory.add("Paris is stored in semantic memory.", kind="semantic")
    hits = memory.search("Paris", k=5, kinds=["semantic"])
    assert len(hits) == 1
    assert hits[0]["kind"] == "semantic"


def test_stats_return_all_memory_tiers(memory):
    stats = memory.stats()
    assert stats["count"] == 0
    assert set(stats["by_kind"].keys()) == set(MEMORY_KINDS)


def test_add_rejects_nonpositive_ttl(memory):
    with pytest.raises(ValueError):
        memory.add("should be rejected", ttl_seconds=0)
    with pytest.raises(ValueError):
        memory.add("also rejected", ttl_seconds=-5)
    assert memory.count() == 0


def test_promote_verified_fact_writes_episodic_and_semantic(memory):
    ids = memory.promote_verified_fact(
        user_input="What is the capital of France?",
        answer="The capital of France is Paris.",
        run_id="abc123",
        verifier_score=0.95,
    )
    assert set(ids.keys()) == {"episodic_id", "semantic_id"}
    assert memory.count(["episodic"]) == 1
    assert memory.count(["semantic"]) == 1
