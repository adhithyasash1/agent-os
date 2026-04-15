"""
Hybrid Memory System — 3-tier: Vector (Chroma), Episodic (Mem0), Graph (Neo4j).

Improvements over v1:
  - Neo4j now stores AND retrieves entity-relationship data (GraphRAG-lite)
  - Mem0 episodic memory is now queryable via search_episodes()
  - Semantic compression: tool outputs distilled to atomic facts before storage
  - Graph queries enriched with entity extraction and relationship traversal
  - Connection lifecycle managed with shutdown hook
"""

import re
import logging
from mem0 import Memory
from langchain_chroma import Chroma
from app.core.config import settings
from app.core.llm import get_embeddings

logger = logging.getLogger("agentos.memory")


class HybridMemory:
    def __init__(self):
        # Episodic Memory (mem0) — local Ollama backend
        mem0_config = {
            "llm": {
                "provider": "ollama",
                "config": {
                    "model": settings.OLLAMA_MODEL,
                    "ollama_base_url": settings.OLLAMA_BASE_URL,
                },
            },
            "embedder": {
                "provider": "ollama",
                "config": {
                    "model": settings.OLLAMA_EMBED_MODEL,
                    "ollama_base_url": settings.OLLAMA_BASE_URL,
                    "embedding_dims": 768,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "embedding_model_dims": 768,
                },
            },
        }
        self.episodic = Memory.from_config(mem0_config)

        # Vector Memory (Chroma)
        self.vector_store = Chroma(
            persist_directory=settings.CHROMA_DB_PATH,
            embedding_function=get_embeddings(),
        )

        # Graph Memory (Neo4j) — optional; skipped if server is unavailable
        self.graph_driver = None
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            driver.verify_connectivity()
            self.graph_driver = driver
            self._ensure_graph_schema()
            logger.info("Neo4j connected.")
        except Exception as e:
            logger.warning(f"Neo4j unavailable, graph memory disabled: {e}")

    # ------------------------------------------------------------------
    # Graph schema setup
    # ------------------------------------------------------------------

    def _ensure_graph_schema(self):
        """Create indexes/constraints for graph memory on first boot."""
        if not self.graph_driver:
            return
        try:
            self.graph_run(
                "CREATE INDEX task_intent IF NOT EXISTS "
                "FOR (t:Task) ON (t.intent)"
            )
            self.graph_run(
                "CREATE INDEX entity_name IF NOT EXISTS "
                "FOR (e:Entity) ON (e.name)"
            )
        except Exception as e:
            logger.warning(f"Graph schema setup skipped: {e}")

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    async def add_episode(self, intent: str, trajectory: list, score: float):
        """Store a completed interaction across all memory tiers."""
        # 1. Episodic (Mem0)
        try:
            summary = self._compress_trajectory(intent, trajectory, score)
            self.episodic.add(summary, user_id="agent_os")
        except Exception as e:
            logger.error(f"mem0 write failed: {e}")

        # 2. Vector (Chroma) — store compressed summary, not raw data
        try:
            self.vector_store.add_texts(
                [f"{intent} -> score={score:.2f}"],
                metadatas=[{"type": "episode", "score": score}],
            )
        except Exception as e:
            logger.error(f"Chroma write failed: {e}")

        # 3. Graph (Neo4j) — extract entities and relationships
        if self.graph_driver:
            try:
                self._store_graph_entities(intent, trajectory, score)
            except Exception as e:
                logger.error(f"Neo4j write failed: {e}")

    def _compress_trajectory(self, intent: str, trajectory: list, score: float) -> str:
        """Semantic compression: distill trajectory to atomic facts."""
        parts = [f"User asked: {intent[:200]}"]
        for t in trajectory:
            tool = t.get("tool", "unknown")
            status = t.get("status", "unknown")
            if status == "success":
                if t.get("results"):
                    parts.append(f"Searched via {tool}: {len(t['results'])} results found")
                elif t.get("content"):
                    parts.append(f"Extracted content via {tool} ({len(t['content'])} chars)")
                elif t.get("mcp_result"):
                    parts.append(f"MCP tool {tool} returned data")
            elif status == "error":
                parts.append(f"{tool} failed: {t.get('error', 'unknown')[:80]}")
        parts.append(f"Final score: {score:.2f}")
        return " | ".join(parts)

    def _store_graph_entities(self, intent: str, trajectory: list, score: float):
        """Extract entities from intent and store relationships in Neo4j."""
        # Extract simple entities (capitalized words, URLs, tool names)
        entities = set()
        # Named entities (capitalized sequences)
        for match in re.findall(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b", intent):
            if len(match) > 2:
                entities.add(match)

        # Tool names from trajectory
        tools_used = set()
        for t in trajectory:
            tool = t.get("tool", "")
            if tool and tool != "none":
                tools_used.add(tool)

        # Use graph_run which handles write transactions properly
        self.graph_run(
            "MERGE (t:Task {intent: $intent}) "
            "SET t.score = $score, t.updated = timestamp()",
            intent=intent[:500], score=score,
        )

        for entity in list(entities)[:10]:
            self.graph_run(
                "MERGE (e:Entity {name: $name}) "
                "MERGE (t:Task {intent: $intent}) "
                "MERGE (t)-[:MENTIONS]->(e)",
                name=entity, intent=intent[:500],
            )

        for tool in tools_used:
            self.graph_run(
                "MERGE (tl:Tool {name: $name}) "
                "MERGE (t:Task {intent: $intent}) "
                "MERGE (t)-[:USED]->(tl)",
                name=tool, intent=intent[:500],
            )

    # ------------------------------------------------------------------
    # Read path — the missing piece from v1
    # ------------------------------------------------------------------

    async def search_episodes(self, query: str, limit: int = 3) -> list[dict]:
        """Query Mem0 episodic memory for relevant past experiences."""
        try:
            results = self.episodic.search(query, user_id="agent_os", limit=limit)
            return [
                {"content": r.get("memory", ""), "score": r.get("score", 0)}
                for r in (results.get("results", []) if isinstance(results, dict) else results)
                if r.get("memory")
            ]
        except Exception as e:
            logger.warning(f"Episodic search failed: {e}")
            return []

    async def search_graph(self, query: str, limit: int = 5) -> list[dict]:
        """Query Neo4j for related entities, tasks, and tools (GraphRAG-lite).

        Performs two-hop traversal:
          1. Find entities mentioned in query
          2. Traverse to related tasks and their connected entities/tools
        """
        if not self.graph_driver:
            return []

        try:
            # Extract potential entity names from query
            query_words = set(re.findall(r"\b([A-Z][a-zA-Z]+)\b", query))
            if not query_words:
                # Fallback: search recent high-scoring tasks
                rows = self.graph_run(
                    "MATCH (t:Task) WHERE t.score >= 0.7 "
                    "RETURN t.intent AS intent, t.score AS score "
                    "ORDER BY t.updated DESC LIMIT $limit",
                    limit=limit,
                )
                if rows:
                    return [
                        {"type": "task", "intent": r["intent"], "score": r["score"]}
                        for r in rows
                    ]
                return []

            # Two-hop entity traversal
            rows = self.graph_run(
                "UNWIND $words AS word "
                "MATCH (e:Entity) WHERE toLower(e.name) CONTAINS toLower(word) "
                "OPTIONAL MATCH (t:Task)-[:MENTIONS]->(e) "
                "OPTIONAL MATCH (t)-[:USED]->(tool:Tool) "
                "OPTIONAL MATCH (t)-[:MENTIONS]->(related:Entity) "
                "RETURN DISTINCT e.name AS entity, "
                "       t.intent AS related_task, t.score AS task_score, "
                "       collect(DISTINCT tool.name) AS tools_used, "
                "       collect(DISTINCT related.name) AS related_entities "
                "ORDER BY task_score DESC "
                "LIMIT $limit",
                words=list(query_words)[:5],
                limit=limit,
            )
            if rows:
                return [
                    {
                        "type": "graph",
                        "entity": r["entity"],
                        "related_task": r["related_task"],
                        "score": r["task_score"],
                        "tools_used": r["tools_used"],
                        "related_entities": r["related_entities"],
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.warning(f"Graph search failed: {e}")
        return []

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def graph_run(self, query: str, **kwargs):
        """Run a Cypher query. Uses explicit write transaction for mutations."""
        if not self.graph_driver:
            return None
        with self.graph_driver.session() as session:
            # Detect if query is a read or write
            q_upper = query.strip().upper()
            if any(q_upper.startswith(kw) for kw in ("MERGE", "CREATE", "DELETE", "SET", "REMOVE")):
                return session.execute_write(lambda tx: tx.run(query, **kwargs).data())
            if "MERGE" in q_upper or "CREATE" in q_upper or "DELETE" in q_upper or "SET " in q_upper:
                return session.execute_write(lambda tx: tx.run(query, **kwargs).data())
            return session.execute_read(lambda tx: tx.run(query, **kwargs).data())

    def vector_count(self) -> int:
        try:
            return self.vector_store._collection.count()
        except Exception:
            return 0

    def episodic_count(self) -> int:
        """Return approximate count of episodic memories."""
        try:
            all_mem = self.episodic.get_all(user_id="agent_os")
            if isinstance(all_mem, dict):
                return len(all_mem.get("results", []))
            return len(all_mem) if all_mem else 0
        except Exception:
            return 0

    def close(self):
        """Clean up connections."""
        if self.graph_driver:
            try:
                self.graph_driver.close()
                logger.info("Neo4j connection closed.")
            except Exception:
                pass


memory = HybridMemory()
