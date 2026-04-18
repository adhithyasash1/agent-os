from __future__ import annotations

import json

import pytest


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "config" in body
    assert "otel" in body["dependencies"]


def test_tools_list(client):
    r = client.get("/api/v1/tools")
    assert r.status_code == 200
    names = [t["name"] for t in r.json()]
    assert "calculator" in names


def test_run_and_fetch(client):
    r = client.post("/api/v1/runs", json={"input": "What is the capital of France?"})
    assert r.status_code == 200
    data = r.json()
    assert "run_id" in data
    assert "Paris" in data["answer"]
    assert data["run_transition_count"] > 0
    assert data["score"] >= 0.6
    run_id = data["run_id"]

    r2 = client.get(f"/api/v1/runs/{run_id}")
    assert r2.status_code == 200
    assert len(r2.json()["events"]) > 0
    assert len(r2.json()["transitions"]) > 0


def test_list_runs_after_create(client):
    client.post("/api/v1/runs", json={"input": "What is the capital of France?"})
    r = client.get("/api/v1/runs")
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_memory_search(client):
    client.post("/api/v1/runs", json={"input": "What is the capital of France?"})
    r = client.post("/api/v1/memory/search", json={"query": "Paris", "k": 3, "kinds": ["semantic"]})
    assert r.status_code == 200
    assert "results" in r.json()


def test_memory_search_rejects_unknown_kind_with_400(client):
    r = client.post("/api/v1/memory/search", json={"query": "Paris", "k": 3, "kinds": ["bogus"]})
    assert r.status_code == 400
    assert "unknown memory kind" in r.json()["detail"]


def test_memory_search_rejects_excessive_kind_filters(client):
    r = client.post(
        "/api/v1/memory/search",
        json={
            "query": "Paris",
            "k": 3,
            "kinds": ["working", "episodic", "semantic", "experience", "style", "failure", "working"],
        },
    )
    assert r.status_code == 400
    assert "too many memory kinds requested" in r.json()["detail"]


def test_memory_stats_have_by_kind(client):
    client.post("/api/v1/runs", json={"input": "What is the capital of France?"})
    r = client.get("/api/v1/memory/stats")
    assert r.status_code == 200
    body = r.json()
    assert "count" in body
    assert "by_kind" in body
    assert "semantic" in body["by_kind"]
    assert "expiring_within_1h" in body


def test_config_patch(client):
    r = client.post("/api/v1/config", json={"enable_tools": False})
    assert r.status_code == 200
    body = r.json()
    assert body["current"]["flags"]["tools"] is False
    assert body["updated"]["enable_tools"] == {"old": True, "new": False}

    r2 = client.get("/api/v1/config")
    assert r2.json()["flags"]["tools"] is False


def test_config_patch_empty_is_noop(client):
    patch_resp = client.post("/api/v1/config", json={})
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["updated"] == {}
    assert "current" in body


def test_settings_budget_validation():
    from agentos.config import Settings

    with pytest.raises(ValueError, match="must sum to less than 1.0"):
        Settings(
            context_developer_ratio=0.5,
            context_scratchpad_ratio=0.5,
            context_tool_ratio=0.1,
        ).apply_profile()


def test_settings_max_steps_default_matches_docs():
    from agentos.config import Settings

    assert Settings.model_fields["max_steps"].default == 4


def test_feedback_endpoint(client):
    run = client.post("/api/v1/runs", json={"input": "What is the capital of France?"}).json()
    r = client.post(
        f"/api/v1/runs/{run['run_id']}/feedback",
        json={"rating": 5, "notes": "Grounded and correct."},
    )
    assert r.status_code == 200
    fetched = client.get(f"/api/v1/runs/{run['run_id']}").json()
    assert fetched["user_feedback"]["rating"] == 5


def test_reject_empty_input(client):
    r = client.post("/api/v1/runs", json={"input": ""})
    assert r.status_code == 422


def test_rlhf_export_returns_jsonl(client):
    chosen = client.post("/api/v1/runs", json={"input": "What is the capital of France?"}).json()
    rejected = client.post("/api/v1/runs", json={"input": "What is the answer to life?"}).json()

    client.post(f"/api/v1/runs/{chosen['run_id']}/feedback", json={"rating": 5, "notes": "Excellent"})
    client.post(f"/api/v1/runs/{rejected['run_id']}/feedback", json={"rating": 1, "notes": "Bad"})

    response = client.get("/api/v1/runs/export")
    assert response.status_code == 200
    lines = [json.loads(line) for line in response.text.splitlines() if line.strip()]
    assert len(lines) == 2
    assert {line["label"] for line in lines} == {"chosen", "rejected"}


async def test_stream_run_completes(async_client):
    run = (
        await async_client.post(
            "/api/v1/runs/async",
            json={"input": "What is the capital of France?"},
        )
    ).json()
    events = []
    async with async_client.stream("GET", f"/api/v1/runs/{run['run_id']}/stream") as response:
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                data = json.loads(line[5:])
                events.append(data)
                if data.get("done"):
                    break
    assert any(e.get("kind") == "final" for e in events if not e.get("done"))
    assert events[-1]["done"] is True
