"""Shared fixtures."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agentos.config import Settings
from agentos.llm.mock import MockLLM
from agentos.memory.store import MemoryStore
from agentos.runtime.trace import TraceStore
from agentos.tools.registry import build_default_registry


@pytest.fixture
def tmp_db(tmp_path: Path) -> str:
    return str(tmp_path / "agentos.db")


@pytest.fixture
def settings(tmp_db) -> Settings:
    s = Settings(db_path=tmp_db, profile="minimal", llm_backend="mock")
    s.apply_profile()
    return s


@pytest.fixture
def memory(tmp_db) -> MemoryStore:
    return MemoryStore(tmp_db)


@pytest.fixture
def traces(tmp_db) -> TraceStore:
    return TraceStore(tmp_db)


@pytest.fixture
def tools(settings):
    return build_default_registry(settings)


@pytest.fixture
def llm():
    return MockLLM()
