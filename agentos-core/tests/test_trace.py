from agentos.runtime.trace import RLTransition, TraceEvent, TraceStore


def test_start_and_finish_run(traces):
    run_id = traces.start_run("hello", "minimal", {"memory": True}, prompt_version="test-v1")
    assert run_id
    traces.log(
        TraceEvent(
            run_id,
            1,
            "understand",
            "input",
            input="hello",
            attributes={"prompt_version": "test-v1"},
        )
    )
    traces.finish_run(run_id, "hi", 0.9, 50, 0, status="ok")

    run = traces.get_run(run_id)
    assert run["user_input"] == "hello"
    assert run["final_output"] == "hi"
    assert run["score"] == 0.9
    assert run["prompt_version"] == "test-v1"
    assert len(run["events"]) == 1
    assert run["events"][0]["kind"] == "understand"
    assert run["events"][0]["attributes"]["prompt_version"] == "test-v1"


def test_list_runs(traces):
    for i in range(3):
        rid = traces.start_run(f"q{i}", "minimal", {}, prompt_version="bench-v1")
        traces.finish_run(rid, "a", 1.0, 10, 0)
    runs = traces.list_runs(limit=10)
    assert len(runs) == 3


def test_rl_transitions_are_returned_with_run(traces):
    run_id = traces.start_run("hello", "minimal", {}, prompt_version="rl-v1")
    traces.log_transition(
        RLTransition(
            run_id=run_id,
            step=1,
            stage="plan",
            state={"prompt": "hello"},
            action={"action": "answer"},
            observation={"packed": True},
            reward=None,
            done=False,
            status="planned",
            attributes={"context_ids": ["memory:1"]},
        )
    )
    traces.finish_run(run_id, "hi", 0.8, 20, 0)
    run = traces.get_run(run_id)
    assert len(run["transitions"]) == 1
    assert run["transitions"][0]["stage"] == "plan"
    assert run["transitions"][0]["attributes"]["context_ids"] == ["memory:1"]
