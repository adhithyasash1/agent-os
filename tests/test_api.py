"""API endpoint tests. Uses FastAPI TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTOS_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("AGENTOS_LLM_BACKEND", "mock")
    monkeypatch.setenv("AGENTOS_PROFILE", "minimal")

    import importlib
    from agentos import config as config_mod

    importlib.reload(config_mod)
    from agentos.api import routes as routes_mod

    importlib.reload(routes_mod)
    from agentos import main as main_mod

    importlib.reload(main_mod)
    return TestClient(main_mod.app)


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
    assert data["status"] == "ok"
    assert "context_ids" in data
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


def test_memory_stats_have_by_kind(client):
    client.post("/api/v1/runs", json={"input": "What is the capital of France?"})
    r = client.get("/api/v1/memory/stats")
    assert r.status_code == 200
    body = r.json()
    assert "count" in body
    assert "by_kind" in body
    assert "semantic" in body["by_kind"]


def test_config_patch(client):
    r = client.post("/api/v1/config", json={"enable_tools": False})
    assert r.status_code == 200
    body = r.json()
    assert body["current"]["flags"]["tools"] is False


def test_feedback_endpoint(client):
    run = client.post("/api/v1/runs", json={"input": "What is the capital of France?"}).json()
    r = client.post(f"/api/v1/runs/{run['run_id']}/feedback", json={"rating": 5, "notes": "Grounded and correct."})
    assert r.status_code == 200
    fetched = client.get(f"/api/v1/runs/{run['run_id']}").json()
    assert fetched["user_feedback"]["rating"] == 5


def test_reject_empty_input(client):
    r = client.post("/api/v1/runs", json={"input": ""})
    assert r.status_code == 422
