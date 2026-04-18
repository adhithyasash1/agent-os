"""Tiered local-first memory store.

This store keeps three memory tiers in SQLite:

- working   : short-lived observations and scratch state
- episodic  : verified task episodes tied to a run
- semantic  : durable verified facts

All tiers share the same FTS index so retrieval can stay simple while the
runtime evolves toward more explicit context engineering.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

from ..config import settings
from ..llm.embeddings import EmbeddingClient, generate_content_hash, normalize_vector
from ..llm.reranker import rerank
from .salience import (
    KIND_BONUS,
    KIND_BONUS_DEFAULT,
    PROMOTED_FACT_SALIENCE_FLOOR,
    UTILITY_LEXICAL_WEIGHT,
    UTILITY_RECENCY_WEIGHT,
    UTILITY_SALIENCE_WEIGHT,
    UTILITY_VERIFIER_WEIGHT,
)


MEMORY_KINDS = ("working", "episodic", "semantic", "experience", "style", "failure")
DEFAULT_TTLS = {
    "working": 60 * 60,
    "episodic": 60 * 60 * 24 * 14,
    "semantic": None,
    "experience": None,
    "style": None,
    "failure": 60 * 60 * 24 * 30, # Failures decay after a month
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
    verifier_score REAL,
    embedding_id TEXT,
    updated_at REAL
);

CREATE TABLE IF NOT EXISTS embeddings (
    id TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    model TEXT NOT NULL,
    vector TEXT NOT NULL,   
    norm REAL NOT NULL,     
    created_at REAL NOT NULL,
    UNIQUE(content_hash, model)
);

CREATE TABLE IF NOT EXISTS retrieval_cache (
    key TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    retrieval_mode TEXT NOT NULL,  
    memory_version INTEGER NOT NULL,
    result_ids TEXT NOT NULL,  
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT,
    description TEXT,
    meta TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS relations (
    subject_id TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_id TEXT NOT NULL,
    meta TEXT,
    created_at REAL NOT NULL,
    PRIMARY KEY (subject_id, predicate, object_id),
    FOREIGN KEY (subject_id) REFERENCES entities(id),
    FOREIGN KEY (object_id) REFERENCES entities(id)
);
"""


class MemoryStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._fts_available = False
        self._local = threading.local()
        self.embed_client = EmbeddingClient(
            base_url=settings.ollama_base_url,
            model=settings.embedding_model,
            api_key=settings.ollama_api_key
        ) if settings.enable_embeddings else None
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            c = sqlite3.connect(self.db_path)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = c
        return self._local.conn

    def purge(self, kind: str | None = None) -> None:
        """Purge memory entries. If kind is None, wipes EVERYTHING."""
        with self._conn() as c:
            if kind:
                c.execute("DELETE FROM memory_entries WHERE kind=?", (kind,))
                if kind == "semantic":
                    c.execute("DELETE FROM entities")
                    c.execute("DELETE FROM relations")
            else:
                c.execute("DELETE FROM memory_entries")
                c.execute("DELETE FROM entities")
                c.execute("DELETE FROM relations")
                c.execute("DELETE FROM retrieval_cache")
                c.execute("DELETE FROM embeddings")
            c.execute("VACUUM")

    def cleanup_expired(self) -> int:
        """Prune expired memory entries based on their TTL.
        Returns the number of rows deleted.
        """
        now = time.time()
        with self._conn() as c:
            cur = c.execute("DELETE FROM memory_entries WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
            count = cur.rowcount
            if count > 0:
                # If we deleted rows, the FTS index needs a refresh
                if self._fts_available:
                    c.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
                # Increment version to invalidate retrieval caches
                c.execute("UPDATE system_state SET value = CAST(value AS INTEGER) + 1 WHERE key = 'memory_version'")
            return count

    def close(self) -> None:
        """Explicitly close the persistent connection."""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(SCHEMA)
            self._ensure_column(c, "memory_entries", "kind", "TEXT NOT NULL DEFAULT 'working'")
            self._ensure_column(c, "memory_entries", "salience", "REAL NOT NULL DEFAULT 0.5")
            self._ensure_column(c, "memory_entries", "ttl_seconds", "INTEGER")
            self._ensure_column(c, "memory_entries", "expires_at", "REAL")
            self._ensure_column(c, "memory_entries", "source_run_id", "TEXT")
            self._ensure_column(c, "memory_entries", "verifier_score", "REAL")
            self._ensure_column(c, "memory_entries", "embedding_id", "TEXT")
            self._ensure_column(c, "memory_entries", "updated_at", "REAL")

            # Insert initial state if missing
            row = c.execute("SELECT value FROM system_state WHERE key = 'memory_version'").fetchone()
            if not row:
                c.execute("INSERT INTO system_state (key, value) VALUES ('memory_version', '1')")

            # Ensure indexes
            c.execute("CREATE INDEX IF NOT EXISTS idx_memory_kind ON memory_entries(kind)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_memory_created_at ON memory_entries(created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_hash_model ON embeddings(content_hash, model)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_retrieval_cache_created_at ON retrieval_cache(created_at)")

            self._migrate_legacy_memory_table(c)
            self._drop_legacy_fts(c)

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

    def _drop_legacy_fts(self, conn: sqlite3.Connection) -> None:
        """Drop an FTS index that predates the tiered-memory schema.

        Older DBs created `memory_fts` as an FTS5 mirror of the `memory` table
        with only the `text` column. The current triggers write `(text, kind)`
        into `memory_fts`, which fails against the legacy definition. If we
        detect the old shape, drop the FTS tables and stale triggers so the
        next CREATE VIRTUAL TABLE (idempotent) rebuilds them correctly.
        """
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='memory_fts'"
        ).fetchone()
        if row and "kind" in (row["sql"] or ""):
            return
        for trigger in ("memory_ai", "memory_ad", "memory_entries_ai",
                        "memory_entries_au", "memory_entries_ad"):
            conn.execute(f"DROP TRIGGER IF EXISTS {trigger}")
        conn.execute("DROP TABLE IF EXISTS memory_fts")

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
        if ttl_seconds is not None and ttl_seconds <= 0:
            # Reject silently-expiring writes. Callers that want "no TTL"
            # must pass None (or rely on the kind default).
            raise ValueError(
                f"ttl_seconds must be positive or None, got {ttl_seconds}"
            )
        ttl_value = DEFAULT_TTLS[kind] if ttl_seconds is None else ttl_seconds
        
        now = time.time()
        expires_at = None if ttl_value is None else now + int(ttl_value)
        
        # 1. Retrieve persistent embeddings cache. Skip embedding if disabled, trivial, or duplicate.
        embedding_id = None
        if settings.enable_embeddings and kind in ("semantic", "experience", "failure") and len(text) > 20 and salience >= 0.1:
            content_hash = generate_content_hash(text)
            model_name = settings.embedding_model
            with self._conn() as c:
                row = c.execute(
                    "SELECT id FROM embeddings WHERE content_hash=? AND model=?", 
                    (content_hash, model_name)
                ).fetchone()
                
                if row:
                    embedding_id = row["id"]
                else:
                    # Cache Miss - Generate vector synchronously
                    raw_vector = self.embed_client.embed_text(text) if self.embed_client else []
                    if raw_vector:
                        vector_normed, norm = normalize_vector(raw_vector)
                        import uuid
                        new_emb_id = str(uuid.uuid4())
                        c.execute(
                            """
                            INSERT INTO embeddings (id, content_hash, model, vector, norm, created_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            (new_emb_id, content_hash, model_name, json.dumps(vector_normed), norm, now)
                        )
                        embedding_id = new_emb_id

        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO memory_entries
                (kind, text, meta, salience, ttl_seconds, created_at, expires_at,
                 source_run_id, tool_used, verifier_score, embedding_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    embedding_id,
                    now,
                ),
            )
            # Increment DB Memory Version
            c.execute("UPDATE system_state SET value = CAST(value AS INTEGER) + 1 WHERE key = 'memory_version'")
            return int(cur.lastrowid)

    def upsert_entity(self, name: str, entity_type: str | None = None, description: str | None = None, meta: dict | None = None) -> str:
        """Upsert a knowledge graph entity."""
        import uuid
        now = time.time()
        # Find existing by name/type or generate ID
        entity_id = hashlib.sha256(f"{name.lower()}:{entity_type.lower() if entity_type else ''}".encode()).hexdigest()[:16]
        
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO entities (id, name, entity_type, description, meta, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    description = COALESCE(?, description),
                    meta = ?,
                    updated_at = ?
                """,
                (entity_id, name, entity_type, description, json.dumps(meta or {}), now, now, description, json.dumps(meta or {}), now)
            )
            return entity_id

    def add_relation(self, subject_id: str, predicate: str, object_id: str, meta: dict | None = None) -> None:
        """Link two entities in the knowledge graph."""
        now = time.time()
        with self._conn() as c:
            c.execute(
                """
                INSERT OR REPLACE INTO relations (subject_id, predicate, object_id, meta, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (subject_id, predicate.lower(), object_id, json.dumps(meta or {}), now)
            )

    def graph_search(self, entity_id: str) -> dict:
        """Retrieve the neighborhood of an entity."""
        with self._conn() as c:
            entity = c.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
            if not entity:
                return {}
                
            out_rel = c.execute(
                "SELECT r.predicate, e.name, e.id FROM relations r JOIN entities e ON r.object_id = e.id WHERE r.subject_id = ?",
                (entity_id,)
            ).fetchall()
            
            in_rel = c.execute(
                "SELECT r.predicate, e.name, e.id FROM relations r JOIN entities e ON r.subject_id = e.id WHERE r.object_id = ?",
                (entity_id,)
            ).fetchall()
            
            return {
                "entity": dict(entity),
                "outbound": [dict(r) for r in out_rel],
                "inbound": [dict(r) for r in in_rel]
            }

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
            salience=max(PROMOTED_FACT_SALIENCE_FLOOR - 0.05, salience),
            ttl_seconds=episodic_ttl_seconds,
            source_run_id=run_id,
            tool_used=tool_used,
            verifier_score=verifier_score,
            meta={"user_input": user_input, "answer": answer},
        )
        semantic_id = self.add(
            answer[:1200],
            kind="semantic",
            salience=max(PROMOTED_FACT_SALIENCE_FLOOR + 0.1, salience),
            ttl_seconds=semantic_ttl_seconds,
            source_run_id=run_id,
            tool_used=tool_used,
            verifier_score=verifier_score,
            meta={"source_question": user_input},
        )
        return {"episodic_id": episodic_id, "semantic_id": semantic_id}

    def record_experience(
        self,
        *,
        user_input: str,
        plan: list[str],
        tool_calls: list[str],
        answer: str,
        run_id: str,
        verifier_score: float,
    ) -> int:
        record = {
            "prompt": user_input,
            "task_type": "demonstration",
            "plan": plan,
            "tool_calls": tool_calls,
            "final_answer": answer,
            "judge_score": verifier_score,
            "success_reason": "Verified completion",
        }
        text = f"Successful Trajectory\nPrompt: {user_input}\nTools: {tool_calls}\nResult: {answer}"
        return self.add(
            text,
            kind="experience",
            salience=max(PROMOTED_FACT_SALIENCE_FLOOR, verifier_score),
            ttl_seconds=None,
            source_run_id=run_id,
            verifier_score=verifier_score,
            meta=record,
        )

    def record_failure(
        self,
        *,
        user_input: str,
        plan: list[str],
        tool_calls: list[str],
        error_or_answer: str,
        run_id: str,
        score: float,
    ) -> int:
        record = {
            "prompt": user_input,
            "plan": plan,
            "tool_calls": tool_calls,
            "error": error_or_answer,
            "judge_score": score,
        }
        text = f"Failure Avoidance\nPrompt: {user_input}\nDead-end: {error_or_answer}"
        return self.add(
            text,
            kind="failure",
            salience=0.3, # Low salience for failures, unless it heavily matches lexically
            ttl_seconds=None,
            source_run_id=run_id,
            verifier_score=score,
            meta=record,
        )

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
        limit = max(k * 5, 12)
        
        mode = settings.retrieval_mode
        if not self._fts_available and mode == "fts":
            mode = "like"
        if not settings.enable_embeddings and mode in ("semantic", "hybrid"):
            mode = "fts" if self._fts_available else "like"

        # 1. Retrieval Cache Lookup
        cache_key = hashlib.sha256(f"{query}:{mode}:{self._get_memory_version()}".encode("utf-8")).hexdigest()
        if settings.retrieval_cache_enabled:
            with self._conn() as c:
                row = c.execute("SELECT result_ids FROM retrieval_cache WHERE key = ?", (cache_key,)).fetchone()
                if row:
                    ids = json.loads(row["result_ids"])
                    if not ids:
                        return []
                    mapped_rows = c.execute(
                        f"SELECT * FROM memory_entries WHERE id IN ({','.join('?' for _ in ids)})", 
                        ids
                    ).fetchall()
                    # Re-map cache returns to Python dictionary structs
                    docs = [dict(r) for r in mapped_rows]
                    # Score and return
                    return self._score_candidates(docs, query)[:k]

        candidates = []
        if mode == "fts":
            candidates = self._fts_search(query, limit, normalized_kinds, min_salience, include_expired)
        elif mode == "like":
            candidates = self._like_search(query, limit, normalized_kinds, min_salience, include_expired)
        elif mode == "semantic":
            candidates = self._semantic_search(query, limit, normalized_kinds, min_salience, include_expired)
        elif mode == "hybrid":
            fts_cand = self._fts_search(query, limit, normalized_kinds, min_salience, include_expired)
            sem_cand = self._semantic_search(query, limit, normalized_kinds, min_salience, include_expired)
            
            # Union deduplicate
            seen_ids = set()
            hybrid_cand = []
            for row in fts_cand + sem_cand:
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
                    hybrid_cand.append(row)
                    
            docs = self._score_candidates([dict(r) for r in hybrid_cand], query)
            
            # Sub-sort semantic priorities explicitly before reranking
            for doc in docs:
                kind_bonus = 1.0
                if doc.get("kind") == "experience": kind_bonus = 1.2
                if doc.get("kind") == "failure": kind_bonus = 1.1
                doc["utility_score"] = float(doc.get("utility_score", 0.0)) * kind_bonus

            if settings.enable_reranker:
                ranked_docs = rerank(query, docs, top_n=settings.rerank_top_n)
                candidates = ranked_docs
            else:
                candidates = docs

        ranked = candidates if isinstance(candidates, list) and candidates and isinstance(candidates[0], dict) and "utility_score" in candidates[0] else self._score_candidates([dict(r) for r in candidates], query)
        
        # Sort if not already handled by Reranker
        if mode != "hybrid" or not settings.enable_reranker:
            ranked.sort(
                key=lambda item: (
                    item.get("utility_score", 0.0),
                    item.get("salience", 0.0),
                    item.get("created_at", 0.0),
                ),
                reverse=True,
            )
            
        final_k = ranked[:k]

        # 2. Cache Results
        if settings.retrieval_cache_enabled:
            final_ids = [d["id"] for d in final_k]
            with self._conn() as c:
                c.execute(
                    """
                    INSERT OR REPLACE INTO retrieval_cache (key, query, retrieval_mode, memory_version, result_ids, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (cache_key, query, mode, self._get_memory_version(), json.dumps(final_ids), time.time())
                )

        return final_k

    def _get_memory_version(self) -> int:
        with self._conn() as c:
            row = c.execute("SELECT value FROM system_state WHERE key = 'memory_version'").fetchone()
            return int(row["value"]) if row else 1

    def _score_candidates(self, candidates: list[dict], query: str) -> list[dict]:
        now = time.time()
        for doc in candidates:
            try:
                doc["meta"] = json.loads(doc.get("meta") or "{}")
            except Exception:
                doc["meta"] = {}
            # Base text scoring pipeline
            doc["utility_score"] = _expected_utility(doc, query, now)
        return candidates

    def _semantic_search(
        self,
        query: str,
        limit: int,
        kinds: tuple[str, ...],
        min_salience: float | None,
        include_expired: bool,
    ) -> list[sqlite3.Row]:
        if not self.embed_client:
            return []
        
        raw_vector = self.embed_client.embed_text(query)
        if not raw_vector:
            return []
            
        query_vector, _ = normalize_vector(raw_vector)
        
        # Pull matching memory targets
        where: list[str] = ["m.embedding_id IS NOT NULL"]
        params: list[Any] = []
        if kinds:
            where.append(f"m.kind IN ({','.join('?' for _ in kinds)})")
            params.extend(kinds)
        if min_salience is not None:
            where.append("m.salience >= ?")
            params.append(float(min_salience))
        if not include_expired:
            where.append("(m.expires_at IS NULL OR m.expires_at > ?)")
            params.append(time.time())

        sql = f"""
            SELECT m.*, e.vector as cached_vector, e.norm as cached_norm
            FROM memory_entries m
            JOIN embeddings e ON m.embedding_id = e.id
            WHERE e.model = ? AND {' AND '.join(where)}
        """
        try:
            with self._conn() as c:
                rows = c.execute(sql, [settings.embedding_model] + params).fetchall()
        except sqlite3.OperationalError:
            return []

        scored_rows = []
        for row in rows:
            vec_json = row["cached_vector"]
            if not vec_json: 
                continue
            try:
                db_vector = json.loads(vec_json)
                # Since both queries and stored vectors are normalized, Cosine similarity = Dot product.
                dot_product = sum(a * b for a, b in zip(query_vector, db_vector))
                
                if dot_product < settings.semantic_min_score:
                    continue
                    
                row_dict = dict(row)
                row_dict["semantic_similarity"] = dot_product
                scored_rows.append(row_dict)
            except Exception:
                continue
                
        scored_rows.sort(key=lambda x: x["semantic_similarity"], reverse=True)
        return scored_rows[:limit]

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
            
            c.execute("UPDATE system_state SET value = CAST(value AS INTEGER) + 1 WHERE key = 'memory_version'")


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
    kind_bonus = KIND_BONUS.get(row.get("kind"), KIND_BONUS_DEFAULT)
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
    return round(
        (lexical * UTILITY_LEXICAL_WEIGHT)
        + (salience * UTILITY_SALIENCE_WEIGHT)
        + (recency * UTILITY_RECENCY_WEIGHT)
        + kind_bonus
        + (verifier * UTILITY_VERIFIER_WEIGHT),
        4,
    )
