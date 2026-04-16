from agentos.runtime.context_packer import pack_context


def test_context_packer_prioritizes_memory_and_tool_chunks():
    packed = pack_context(
        user_input="What powers agentos-core by default?",
        memory_hits=[
            {
                "id": 1,
                "kind": "semantic",
                "text": "agentos-core uses SQLite as the default store.",
                "salience": 0.9,
                "utility_score": 1.2,
                "source_run_id": "r1",
            }
        ],
        tool_results=[
            {
                "tool": "calculator",
                "status": "ok",
                "output": 132,
                "observation_summary": "Computed the requested arithmetic result.",
                "iteration": 1,
            }
        ],
        critique="Be more grounded in the retrieved note.",
        prior_decisions=[],
        budget_chars=2200,
        prompt_version="test-prompt",
    )
    assert "developer:instructions" in packed.included_ids
    assert "memory:1" in packed.included_ids
    assert any(chunk_id.startswith("tool:") for chunk_id in packed.included_ids)
    assert packed.prompt_version == "test-prompt"
    assert "SQLite" in packed.rendered
