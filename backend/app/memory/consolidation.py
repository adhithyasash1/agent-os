"""
Memory Consolidation — offline "dreaming" for stored memories.

Biological analog: sleep consolidation. Between active sessions, the system:
  1. Finds near-duplicate memories and merges them
  2. Detects contradictions in the knowledge graph
  3. Prunes low-value entries below a utility threshold
  4. Compresses verbose episodic memories into tighter summaries

Can be triggered manually via API or automatically after N interactions.
"""

import logging
import re
from datetime import datetime
from typing import Any

from app.core.llm import get_llm
from app.core.config import settings
from langchain_core.messages import SystemMessage

logger = logging.getLogger("agentos.consolidation")


async def consolidate_memories(memory) -> dict[str, Any]:
    """Run full memory consolidation cycle.

    Args:
        memory: HybridMemory instance

    Returns:
        Report dict with counts of actions taken.
    """
    report = {
        "started_at": datetime.now().isoformat(),
        "duplicates_merged": 0,
        "contradictions_resolved": 0,
        "low_value_pruned": 0,
        "episodes_compressed": 0,
        "errors": [],
    }

    # --- Phase 1: Deduplicate vector store ---
    try:
        dedup_count = await _deduplicate_vectors(memory)
        report["duplicates_merged"] = dedup_count
    except Exception as e:
        logger.error(f"Vector dedup failed: {e}")
        report["errors"].append(f"dedup: {e}")

    # --- Phase 2: Detect & resolve graph contradictions ---
    try:
        contradiction_count = await _resolve_graph_contradictions(memory)
        report["contradictions_resolved"] = contradiction_count
    except Exception as e:
        logger.error(f"Contradiction resolution failed: {e}")
        report["errors"].append(f"contradictions: {e}")

    # --- Phase 3: Prune low-value graph nodes ---
    try:
        prune_count = _prune_low_value_tasks(memory)
        report["low_value_pruned"] = prune_count
    except Exception as e:
        logger.error(f"Pruning failed: {e}")
        report["errors"].append(f"prune: {e}")

    # --- Phase 4: Compress verbose episodic memories ---
    try:
        compress_count = await _compress_episodic_memories(memory)
        report["episodes_compressed"] = compress_count
    except Exception as e:
        logger.error(f"Episodic compression failed: {e}")
        report["errors"].append(f"compress: {e}")

    # --- Phase 5: Compile entity truths ---
    try:
        compiled_count = await _compile_all_entity_truths(memory)
        report["truths_compiled"] = compiled_count
    except Exception as e:
        logger.error(f"Truth compilation failed: {e}")
        report["errors"].append(f"compile: {e}")

    report["completed_at"] = datetime.now().isoformat()
    logger.info(
        f"Consolidation complete: {report['duplicates_merged']} merged, "
        f"{report['contradictions_resolved']} contradictions, "
        f"{report['low_value_pruned']} pruned, "
        f"{report['episodes_compressed']} compressed, "
        f"{report.get('truths_compiled', 0)} truths compiled"
    )
    return report


async def _deduplicate_vectors(memory) -> int:
    """Find and merge near-duplicate entries in Chroma.

    Strategy: For each document, search for similar docs. If cosine similarity
    is very high (>0.95) and content is nearly identical, remove the duplicate
    and keep the one with the higher score metadata.
    """
    merged = 0
    try:
        collection = memory.vector_store._collection
        count = collection.count()
        if count < 2:
            return 0

        # Get all documents with their IDs and metadata
        all_docs = collection.get(include=["documents", "metadatas", "embeddings"])
        if not all_docs or not all_docs.get("documents"):
            return 0

        documents = all_docs["documents"]
        ids = all_docs["ids"]
        metadatas = all_docs.get("metadatas", [{}] * len(documents))

        # Track which IDs to remove (duplicates)
        to_remove = set()
        seen_content = {}  # normalized content → best ID

        for i, doc in enumerate(documents):
            if ids[i] in to_remove:
                continue

            # Normalize for comparison: lowercase, strip whitespace, collapse spaces
            normalized = re.sub(r"\s+", " ", doc.strip().lower())

            # Check for near-exact duplicates (same content after normalization)
            if normalized in seen_content:
                # Keep the one with higher score
                existing_idx = seen_content[normalized]
                existing_score = (metadatas[existing_idx] or {}).get("score", 0)
                current_score = (metadatas[i] or {}).get("score", 0)

                if current_score > existing_score:
                    to_remove.add(ids[existing_idx])
                    seen_content[normalized] = i
                else:
                    to_remove.add(ids[i])
                merged += 1
            else:
                seen_content[normalized] = i

        # Remove duplicates
        if to_remove:
            collection.delete(ids=list(to_remove))
            logger.info(f"  Removed {len(to_remove)} duplicate vectors")

    except Exception as e:
        logger.warning(f"  Vector dedup error: {e}")

    return merged


async def _resolve_graph_contradictions(memory) -> int:
    """Find contradictory relationships in Neo4j and resolve them.

    Contradiction: same entity linked to tasks with conflicting information.
    Resolution: keep the relationship from the higher-scoring task.
    """
    if not memory.graph_driver:
        return 0

    resolved = 0
    try:
        # Find entities mentioned in multiple tasks with different scores
        rows = memory.graph_run(
            "MATCH (t1:Task)-[:MENTIONS]->(e:Entity)<-[:MENTIONS]-(t2:Task) "
            "WHERE id(t1) < id(t2) "
            "AND t1.score IS NOT NULL AND t2.score IS NOT NULL "
            "AND abs(t1.score - t2.score) > 0.3 "
            "RETURN e.name AS entity, "
            "       t1.intent AS task1, t1.score AS score1, "
            "       t2.intent AS task2, t2.score AS score2 "
            "LIMIT 20"
        )

        if not rows:
            return 0

        llm = get_llm()
        for row in rows:
            entity = row["entity"]
            task1 = row["task1"][:200]
            task2 = row["task2"][:200]
            score1 = row["score1"]
            score2 = row["score2"]

            # Ask LLM if these tasks contain contradictory information about the entity
            prompt = (
                f"Do these two statements about '{entity}' contradict each other?\n"
                f"Statement 1 (score {score1:.2f}): {task1}\n"
                f"Statement 2 (score {score2:.2f}): {task2}\n\n"
                f"Answer ONLY 'YES' or 'NO'."
            )

            try:
                result = await llm.ainvoke(prompt)
                answer = result.content.strip().upper()

                if "YES" in answer:
                    # Remove relationship from lower-scoring task
                    loser_intent = task1 if score1 < score2 else task2
                    memory.graph_run(
                        "MATCH (t:Task {intent: $intent})-[r:MENTIONS]->(e:Entity {name: $name}) "
                        "DELETE r",
                        intent=loser_intent, name=entity,
                    )
                    resolved += 1
                    logger.info(
                        f"  Resolved contradiction: '{entity}' — "
                        f"removed link from lower-scoring task"
                    )
            except Exception as e:
                logger.warning(f"  Contradiction check failed for '{entity}': {e}")

    except Exception as e:
        logger.warning(f"  Graph contradiction scan error: {e}")

    return resolved


def _prune_low_value_tasks(memory, score_threshold: float = None) -> int:
    """Remove Task nodes (and their edges) with very low scores.

    Only prunes tasks below the threshold — preserves Entity and Tool nodes
    even if they lose some task connections.
    """
    if score_threshold is None:
        score_threshold = settings.CONSOLIDATION_PRUNE_THRESHOLD

    if not memory.graph_driver:
        return 0

    pruned = 0
    try:
        # Count before
        rows = memory.graph_run(
            "MATCH (t:Task) WHERE t.score IS NOT NULL AND t.score < $threshold "
            "RETURN count(t) AS cnt",
            threshold=score_threshold,
        )
        count = rows[0]["cnt"] if rows else 0

        if count > 0:
            # Delete low-scoring tasks and their relationships
            memory.graph_run(
                "MATCH (t:Task) WHERE t.score IS NOT NULL AND t.score < $threshold "
                "DETACH DELETE t",
                threshold=score_threshold,
            )
            pruned = count
            logger.info(f"  Pruned {pruned} low-scoring tasks (< {score_threshold})")

        # Clean up orphaned entities (no remaining task connections)
        orphan_rows = memory.graph_run(
            "MATCH (e:Entity) WHERE NOT (e)<-[:MENTIONS]-() "
            "RETURN count(e) AS cnt"
        )
        orphan_count = orphan_rows[0]["cnt"] if orphan_rows else 0
        if orphan_count > 0:
            memory.graph_run(
                "MATCH (e:Entity) WHERE NOT (e)<-[:MENTIONS]-() DELETE e"
            )
            logger.info(f"  Cleaned {orphan_count} orphaned entities")

    except Exception as e:
        logger.warning(f"  Pruning error: {e}")

    return pruned


async def _compress_episodic_memories(memory) -> int:
    """Compress verbose episodic memories into tighter summaries.

    Finds long episodic entries and asks the LLM to compress them
    while preserving key facts.
    """
    compressed = 0
    try:
        all_memories = memory.episodic.get_all(user_id="agent_os")
        if isinstance(all_memories, dict):
            memories = all_memories.get("results", [])
        elif isinstance(all_memories, list):
            memories = all_memories
        else:
            return 0

        llm = get_llm()

        for mem in memories:
            content = mem.get("memory", "")
            mem_id = mem.get("id", "")

            # Only compress verbose entries
            if not content or len(content) < settings.CONSOLIDATION_COMPRESS_MIN_CHARS or not mem_id:
                continue

            try:
                prompt = (
                    "Compress the following memory into a single concise sentence "
                    "that preserves ALL key facts (entities, tools, scores, outcomes). "
                    "Remove filler words and redundancy.\n\n"
                    f"MEMORY: {content[:1000]}\n\n"
                    "COMPRESSED (one sentence):"
                )
                result = await llm.ainvoke(prompt)
                shorter = result.content.strip()

                # Only update if actually shorter
                if shorter and len(shorter) < len(content) * 0.7:
                    memory.episodic.update(mem_id, shorter)
                    compressed += 1
                    logger.debug(
                        f"  Compressed memory {mem_id}: "
                        f"{len(content)} → {len(shorter)} chars"
                    )
            except Exception as e:
                logger.warning(f"  Failed to compress memory {mem_id}: {e}")

    except Exception as e:
        logger.warning(f"  Episodic compression error: {e}")

    return compressed


async def _compile_all_entity_truths(memory) -> int:
    """Compile truth summaries for all entities that lack one.

    Finds Entity nodes where `summary` is null or missing, then calls
    the HybridMemory compiled truth method to generate a summary from
    all linked tasks.
    """
    if not memory.graph_driver:
        return 0

    compiled = 0
    try:
        # Find entities without compiled truths
        rows = memory.graph_run(
            "MATCH (e:Entity) WHERE e.summary IS NULL "
            "RETURN e.name AS name LIMIT 20"
        )

        if not rows:
            logger.info("  All entities already have compiled truths")
            return 0

        entity_names = {r["name"] for r in rows}
        logger.info(f"  Compiling truths for {len(entity_names)} entities")

        await memory._compile_entity_truths(entity_names)
        compiled = len(entity_names)

    except Exception as e:
        logger.warning(f"  Entity truth compilation error: {e}")

    return compiled
