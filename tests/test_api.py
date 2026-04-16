"""API endpoint tests. Uses FastAPI TestClient.

Because components are built at lifespan startup and injected via
`Depends`, we can build a fresh app per test with no module reloads.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentos.api import api_router, build_components
from agentos.config import Settings


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "api.db"),
        llm_backend="mock",
        profile="minimal",
    )
    settings.apply_profile()
    app = FastAPI(title="agentos-core-test")
    app.include_router(api_router, prefix=settings.api_prefix)
    app.state.components = build_components(settings)
    return TestClient(app)


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
    assert body["updated"]["enable_tools"] == {"old": True, "new": False}

    r2 = client.get("/api/v1/config")
    assert r2.json()["flags"]["tools"] is False


def test_config_patch_empty_is_noop(client):
    r = client.post("/api/v1/config", json={})
    assert r.status_code == 200
    assert r.json()["updated"] == {}


def test_feedback_endpoint(client):
    run = client.post("/api/v1/runs", json={"input": "What is the capital of France?"}).json()
    r = client.post(f"/api/v1/runs/{run['run_id']}/feedback", json={"rating": 5, "notes": "Grounded and correct."})
    assert r.status_code == 200
    fetched = client.get(f"/api/v1/runs/{run['run_id']}").json()
    assert fetched["user_feedback"]["rating"] == 5


def test_reject_empty_input(client):
    r = client.post("/api/v1/runs", json={"input": ""})
    assert r.status_code == 422
