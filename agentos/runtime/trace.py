"""SQLite-backed trace and RL transition store."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    user_input TEXT NOT NULL,
    final_output TEXT,
    score REAL,
    profile TEXT,
    flags TEXT,
    prompt_version TEXT,
    user_feedback TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    total_latency_ms INTEGER,
    total_tokens INTEGER,
    status TEXT DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS trace_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    kind TEXT NOT NULL,
    name TEXT,
    input TEXT,
    output TEXT,
    latency_ms INTEGER,
    tokens_in INTEGER,
    tokens_out INTEGER,
    error TEXT,
    attributes TEXT,
    ts TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS rl_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    stage TEXT NOT NULL,
    state TEXT,
    action TEXT,
    observation TEXT,
    reward REAL,
    done INTEGER DEFAULT 0,
    status TEXT,
    attributes TEXT,
    ts TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_events_run ON trace_events(run_id, step);
CREATE INDEX IF NOT EXISTS idx_rl_run ON rl_transitions(run_id, step);
"""


@dataclass
class TraceEvent:
    run_id: str
    step: int
    kind: str
    name: str | None = None
    input: Any = None
    output: Any = None
    latency_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    error: str | None = None
    attributes: dict[str, Any] | None = None
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_row(self) -> tuple:
        return (
            self.run_id,
            self.step,
            self.kind,
            self.name,
            _dumps(self.input),
            _dumps(self.output),
            self.latency_ms,
            self.tokens_in,
            self.tokens_out,
            self.error,
            _dumps(self.attributes),
            self.ts,
        )


@dataclass
class RLTransition:
    run_id: str
    step: int
    stage: str
    state: Any = None
    action: Any = None
    observation: Any = None
    reward: float | None = None
    done: bool = False
    status: str | None = None
    attributes: dict[str, Any] | None = None
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_row(self) -> tuple:
        return (
            self.run_id,
            self.step,
            self.stage,
            _dumps(self.state),
            _dumps(self.action),
            _dumps(self.observation),
            self.reward,
            1 if self.done else 0,
            self.status,
            _dumps(self.attributes),
            self.ts,
        )


def _dumps(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v[:12000]
    try:
        return json.dumps(v, default=str)[:12000]
    except Exception:
        return str(v)[:12000]


class TraceStore:
    def __init__(self, db_path: str, config: Any | None = None):
        self.db_path = db_path
        self.config = config
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)
            self._ensure_column(c, "runs", "prompt_version", "TEXT")
            self._ensure_column(c, "runs", "user_feedback", "TEXT")
            self._ensure_column(c, "trace_events", "attributes", "TEXT")
        self._otel = _OTelBridge(config)

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        cols = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    @property
    def otel_enabled(self) -> bool:
        return self._otel.enabled

    def start_run(self, user_input: str, profile: str, flags: dict, prompt_version: str = "v1") -> str:
        run_id = uuid.uuid4().hex[:12]
        started_at = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO runs
                (run_id, user_input, profile, flags, prompt_version, started_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, user_input, profile, json.dumps(flags), prompt_version, started_at),
            )
        self._otel.start_run(run_id, profile=profile, prompt_version=prompt_version, flags=flags)
        return run_id

    def finish_run(
        self,
        run_id: str,
        final_output: str,
        score: float,
        total_latency_ms: int,
        total_tokens: int,
        status: str = "ok",
    ) -> None:
        finished_at = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                """UPDATE runs SET final_output=?, score=?, finished_at=?,
                   total_latency_ms=?, total_tokens=?, status=? WHERE run_id=?""",
                (final_output, score, finished_at, total_latency_ms, total_tokens, status, run_id),
            )
        self._otel.finish_run(run_id, score=score, total_latency_ms=total_latency_ms, total_tokens=total_tokens, status=status)

    def log(self, event: TraceEvent) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO trace_events
                   (run_id, step, kind, name, input, output, latency_ms,
                    tokens_in, tokens_out, error, attributes, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                event.to_row(),
            )
        self._otel.log_event(event)

    def log_transition(self, transition: RLTransition) -> None:
        with self._conn() as c:
            c.execute(
                """INSERT INTO rl_transitions
                   (run_id, step, stage, state, action, observation, reward,
                    done, status, attributes, ts)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                transition.to_row(),
            )

    def record_feedback(self, run_id: str, feedback: dict[str, Any]) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE runs SET user_feedback=? WHERE run_id=?",
                (json.dumps(feedback), run_id),
            )
        self._otel.annotate_run(run_id, {"user_feedback": feedback})

    def list_runs(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_run(self, run_id: str) -> dict | None:
        with self._conn() as c:
            run = c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if not run:
                return None
            events = c.execute(
                "SELECT * FROM trace_events WHERE run_id=? ORDER BY step, id",
                (run_id,),
            ).fetchall()
            transitions = c.execute(
                "SELECT * FROM rl_transitions WHERE run_id=? ORDER BY step, id",
                (run_id,),
            ).fetchall()
        data = dict(run)
        data["events"] = [_loads_row(dict(event)) for event in events]
        data["transitions"] = [_loads_row(dict(transition)) for transition in transitions]
        if data.get("user_feedback"):
            try:
                data["user_feedback"] = json.loads(data["user_feedback"])
            except Exception:
                pass
        return data


def _loads_row(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("input", "output", "state", "action", "observation", "attributes"):
        value = row.get(key)
        if not value or not isinstance(value, str):
            continue
        try:
            row[key] = json.loads(value)
        except Exception:
            row[key] = value
    return row


class Timer:
    """Context manager for measuring wall-clock latency."""
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.ms = int((time.perf_counter() - self.start) * 1000)


class _OTelBridge:
    def __init__(self, config: Any | None):
        self.enabled = False
        self._run_spans: dict[str, Any] = {}
        if not config or not getattr(config, "enable_otel", False):
            return
        try:
            from opentelemetry import trace as otel_trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
        except Exception:
            return

        provider = TracerProvider(
            resource=Resource.create({"service.name": getattr(config, "otel_service_name", "agentos-core")})
        )
        endpoint = getattr(config, "otel_exporter_otlp_endpoint", "") or ""
        exporter = None
        if endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

                exporter = OTLPSpanExporter(endpoint=endpoint)
            except Exception:
                exporter = None
        if exporter is None:
            exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(exporter))
        try:
            otel_trace.set_tracer_provider(provider)
        except Exception:
            pass

        self._trace = otel_trace
        self._tracer = otel_trace.get_tracer(getattr(config, "otel_service_name", "agentos-core"))
        self.enabled = True

    def start_run(self, run_id: str, **attributes: Any) -> None:
        if not self.enabled:
            return
        span = self._tracer.start_span("agent.run", attributes=_otel_attributes({"run_id": run_id, **attributes}))
        self._run_spans[run_id] = span

    def annotate_run(self, run_id: str, attributes: dict[str, Any]) -> None:
        if not self.enabled:
            return
        span = self._run_spans.get(run_id)
        if not span:
            return
        for key, value in _otel_attributes(attributes).items():
            span.set_attribute(key, value)

    def log_event(self, event: TraceEvent) -> None:
        if not self.enabled:
            return
        parent = self._run_spans.get(event.run_id)
        context = self._trace.set_span_in_context(parent) if parent else None
        span = self._tracer.start_span(
            f"agent.{event.kind}",
            context=context,
            attributes=_otel_attributes(
                {
                    "run_id": event.run_id,
                    "step": event.step,
                    "kind": event.kind,
                    "name": event.name,
                    "latency_ms": event.latency_ms,
                    "error": event.error,
                    **(event.attributes or {}),
                }
            ),
        )
        span.end()

    def finish_run(self, run_id: str, **attributes: Any) -> None:
        if not self.enabled:
            return
        span = self._run_spans.pop(run_id, None)
        if not span:
            return
        for key, value in _otel_attributes(attributes).items():
            span.set_attribute(key, value)
        span.end()


def _otel_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in attributes.items():
        if value is None:
            continue
        if isinstance(value, (str, bool, int, float)):
            out[key] = value
        else:
            out[key] = json.dumps(value, default=str)[:4000]
    return out
