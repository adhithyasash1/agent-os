"""Tiered local-first memory store.

This store keeps three memory tiers in SQLite:

- working   : short-lived observations and scratch state
- episodic  : verified task episodes tied to a run
- semantic  : durable verified facts

All tiers share the same FTS index so retrieval can stay simple while the
runtime evolves toward more explicit context engineering.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable


MEMORY_KINDS = ("working", "episodic", "semantic")
DEFAULT_TTLS = {
    "working": 60 * 60,
    "episodic": 60 * 60 * 24 * 14,
    "semantic": None,
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL DEFAULT 'working',
    text TEXT NOT NULL,
    meta TEXT,
    salience REAL NOT NULL DEFAULT 0.5,
    ttl_seconds INTEGER,
    created_at REAL NOT NULL,
    expires_at REAL,
    source_run_id TEXT,
    tool_used TEXT,
    verifier_score REAL
);
"""


class MemoryStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._fts_available = False
        self._init_schema()

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.execute(SCHEMA)
            self._ensure_column(c, "memory_entries", "kind", "TEXT NOT NULL DEFAULT 'working'")
            self._ensure_column(c, "memory_entries", "salience", "REAL NOT NULL DEFAULT 0.5")
            self._ensure_column(c, "memory_entries", "ttl_seconds", "INTEGER")
            self._ensure_column(c, "memory_entries", "expires_at", "REAL")
            self._ensure_column(c, "memory_entries", "source_run_id", "TEXT")
            self._ensure_column(c, "memory_entries", "tool_used", "TEXT")
            self._ensure_column(c, "memory_entries", "verifier_score", "REAL")

            self._migrate_legacy_memory_table(c)

            try:
                c.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                    USING fts5(text, kind UNINDEXED, content='memory_entries', content_rowid='id')
                    """
                )
                c.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS memory_entries_ai
                    AFTER INSERT ON memory_entries BEGIN
                      INSERT INTO memory_fts(rowid, text, kind)
                      VALUES (new.id, new.text, new.kind);
                    END
                    """
                )
                c.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS memory_entries_au
                    AFTER UPDATE ON memory_entries BEGIN
                      INSERT INTO memory_fts(memory_fts, rowid, text, kind)
                      VALUES('delete', old.id, old.text, old.kind);
                      INSERT INTO memory_fts(rowid, text, kind)
                      VALUES (new.id, new.text, new.kind);
                    END
                    """
                )
                c.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS memory_entries_ad
                    AFTER DELETE ON memory_entries BEGIN
                      INSERT INTO memory_fts(memory_fts, rowid, text, kind)
                      VALUES('delete', old.id, old.text, old.kind);
                    END
                    """
                )
                c.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
                self._fts_available = True
            except sqlite3.OperationalError:
                self._fts_available = False

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        cols = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _table_exists(self, conn: sqlite3.Connection, table: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return row is not None

    def _migrate_legacy_memory_table(self, conn: sqlite3.Connection) -> None:
        if not self._table_exists(conn, "memory"):
            return
        current_count = conn.execute("SELECT COUNT(*) AS n FROM memory_entries").fetchone()["n"]
        if current_count:
            return
        rows = conn.execute(
            "SELECT text, meta, created_at FROM memory ORDER BY id"
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT INTO memory_entries
                (kind, text, meta, salience, ttl_seconds, created_at, expires_at,
                 source_run_id, tool_used, verifier_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "semantic",
                    row["text"],
                    row["meta"],
                    0.7,
                    None,
                    row["created_at"],
                    None,
                    None,
                    None,
                    None,
                ),
            )

    def add(
        self,
        text: str,
        meta: dict | None = None,
        *,
        kind: str = "working",
        salience: float = 0.5,
        ttl_seconds: int | None = None,
        source_run_id: str | None = None,
        tool_used: str | None = None,
        verifier_score: float | None = None,
    ) -> int:
        kind = _normalize_kind(kind)
        ttl_value = DEFAULT_TTLS[kind] if ttl_seconds is None else ttl_seconds
        now = time.time()
        expires_at = None if ttl_value is None else now + max(int(ttl_value), 0)
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO memory_entries
                (kind, text, meta, salience, ttl_seconds, created_at, expires_at,
                 source_run_id, tool_used, verifier_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    kind,
                    text,
                    json.dumps(meta or {}),
                    _clamp_salience(salience),
                    ttl_value,
                    now,
                    expires_at,
                    source_run_id,
                    tool_used,
                    verifier_score,
                ),
            )
            return int(cur.lastrowid)

    def promote_verified_fact(
        self,
        *,
        user_input: str,
        answer: str,
        run_id: str,
        tool_used: str | None = None,
        verifier_score: float | None = None,
        salience: float = 0.8,
        episodic_ttl_seconds: int | None = None,
        semantic_ttl_seconds: int | None = None,
    ) -> dict[str, int]:
        episodic_id = self.add(
            f"Episode\nUser: {user_input}\nVerified answer: {answer}",
            kind="episodic",
            salience=max(0.65, salience),
            ttl_seconds=episodic_ttl_seconds,
            source_run_id=run_id,
            tool_used=tool_used,
            verifier_score=verifier_score,
            meta={"user_input": user_input, "answer": answer},
        )
        semantic_id = self.add(
            answer[:1200],
            kind="semantic",
            salience=max(0.8, salience),
            ttl_seconds=semantic_ttl_seconds,
            source_run_id=run_id,
            tool_used=tool_used,
            verifier_score=verifier_score,
            meta={"source_question": user_input},
        )
        return {"episodic_id": episodic_id, "semantic_id": semantic_id}

    def search(
        self,
        query: str,
        k: int = 3,
        *,
        kinds: Iterable[str] | None = None,
        min_salience: float | None = None,
        include_expired: bool = False,
    ) -> list[dict]:
        query = (query or "").strip()
        if not query:
            return []

        normalized_kinds = tuple(_normalize_kind(kind) for kind in (kinds or MEMORY_KINDS))
        candidates = (
            self._fts_search(query, max(k * 5, 12), normalized_kinds, min_salience, include_expired)
            if self._fts_available
            else self._like_search(query, max(k * 5, 12), normalized_kinds, min_salience, include_expired)
        )

        ranked: list[dict] = []
        now = time.time()
        for row in candidates:
            doc = dict(row)
            try:
                doc["meta"] = json.loads(doc.get("meta") or "{}")
            except Exception:
                doc["meta"] = {}
            doc["utility_score"] = _expected_utility(doc, query, now)
            ranked.append(doc)

        ranked.sort(
            key=lambda item: (
                item.get("utility_score", 0.0),
                item.get("salience", 0.0),
                item.get("created_at", 0.0),
            ),
            reverse=True,
        )
        return ranked[:k]

    def _fts_search(
        self,
        query: str,
        limit: int,
        kinds: tuple[str, ...],
        min_salience: float | None,
        include_expired: bool,
    ) -> list[sqlite3.Row]:
        where: list[str] = ["memory_fts MATCH ?"]
        params: list[Any] = [_build_match_query(query)]
        if kinds:
            where.append(f"m.kind IN ({','.join('?' for _ in kinds)})")
            params.extend(kinds)
        if min_salience is not None:
            where.append("m.salience >= ?")
            params.append(float(min_salience))
        if not include_expired:
            where.append("(m.expires_at IS NULL OR m.expires_at > ?)")
            params.append(time.time())
        params.append(limit)
        sql = f"""
            SELECT m.*, bm25(memory_fts) AS fts_rank
            FROM memory_fts
            JOIN memory_entries m ON m.id = memory_fts.rowid
            WHERE {' AND '.join(where)}
            ORDER BY bm25(memory_fts)
            LIMIT ?
        """
        try:
            with self._conn() as c:
                return c.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return self._like_search(query, limit, kinds, min_salience, include_expired)

    def _like_search(
        self,
        query: str,
        limit: int,
        kinds: tuple[str, ...],
        min_salience: float | None,
        include_expired: bool,
    ) -> list[sqlite3.Row]:
        where: list[str] = ["text LIKE ?"]
        params: list[Any] = [f"%{query.strip()}%"]
        if kinds:
            where.append(f"kind IN ({','.join('?' for _ in kinds)})")
            params.extend(kinds)
        if min_salience is not None:
            where.append("salience >= ?")
            params.append(float(min_salience))
        if not include_expired:
            where.append("(expires_at IS NULL OR expires_at > ?)")
            params.append(time.time())
        params.append(limit)
        sql = f"""
            SELECT *, NULL AS fts_rank
            FROM memory_entries
            WHERE {' AND '.join(where)}
            ORDER BY salience DESC, created_at DESC
            LIMIT ?
        """
        with self._conn() as c:
            return c.execute(sql, params).fetchall()

    def count(self, kinds: Iterable[str] | None = None) -> int:
        normalized_kinds = tuple(_normalize_kind(kind) for kind in kinds) if kinds else ()
        with self._conn() as c:
            if normalized_kinds:
                row = c.execute(
                    f"SELECT COUNT(*) AS n FROM memory_entries WHERE kind IN ({','.join('?' for _ in normalized_kinds)})",
                    normalized_kinds,
                ).fetchone()
            else:
                row = c.execute("SELECT COUNT(*) AS n FROM memory_entries").fetchone()
        return int(row["n"])

    def stats(self) -> dict:
        with self._conn() as c:
            total = int(c.execute("SELECT COUNT(*) AS n FROM memory_entries").fetchone()["n"])
            rows = c.execute(
                "SELECT kind, COUNT(*) AS n FROM memory_entries GROUP BY kind"
            ).fetchall()
        by_kind = {kind: 0 for kind in MEMORY_KINDS}
        for row in rows:
            by_kind[row["kind"]] = int(row["n"])
        return {"count": total, "by_kind": by_kind}

    def clear(self, kinds: Iterable[str] | None = None) -> None:
        normalized_kinds = tuple(_normalize_kind(kind) for kind in kinds) if kinds else ()
        with self._conn() as c:
            if normalized_kinds:
                c.execute(
                    f"DELETE FROM memory_entries WHERE kind IN ({','.join('?' for _ in normalized_kinds)})",
                    normalized_kinds,
                )
            else:
                c.execute("DELETE FROM memory_entries")
            if self._fts_available:
                c.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")


def _normalize_kind(kind: str) -> str:
    value = (kind or "working").strip().lower()
    if value not in MEMORY_KINDS:
        raise ValueError(f"unknown memory kind: {kind}")
    return value


def _clamp_salience(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split()
        if len(token) >= 3
    ]


def _build_match_query(query: str) -> str:
    tokens = _tokenize(query)[:8]
    if not tokens:
        return f'"{query.replace(chr(34), " ").strip()}"'
    if len(tokens) == 1:
        return tokens[0]
    return " OR ".join(tokens)


def _expected_utility(row: dict, query: str, now: float) -> float:
    kind_bonus = {"working": 0.16, "episodic": 0.26, "semantic": 0.36}.get(row.get("kind"), 0.1)
    salience = float(row.get("salience") or 0.0)
    created_at = float(row.get("created_at") or now)
    age_hours = max(0.0, (now - created_at) / 3600)
    recency = 1 / (1 + age_hours / 24)
    lexical = 0.15
    fts_rank = row.get("fts_rank")
    if isinstance(fts_rank, (int, float)):
        lexical = 1 / (1 + max(float(fts_rank), 0.0))
    else:
        text = (row.get("text") or "").lower()
        query_tokens = set(_tokenize(query))
        text_tokens = set(_tokenize(text))
        if query_tokens:
            lexical = len(query_tokens & text_tokens) / len(query_tokens)
    verifier = float(row.get("verifier_score") or 0.0)
    return round((lexical * 0.38) + (salience * 0.32) + (recency * 0.14) + kind_bonus + (verifier * 0.08), 4)
