"""
Reranker — FlashRank cross-encoder reranking for retrieval quality.

Sits between vector similarity search (Chroma top-k) and context assembly.
Re-scores candidates with a cross-encoder model, reorders by relevance.

Model: ms-marco-MiniLM-L-12-v2 (~33MB, CPU-only, <50ms per batch)
"""

import logging
from typing import Optional

logger = logging.getLogger("agentos.reranker")

_ranker = None


def _get_ranker():
    """Lazy-init FlashRank ranker (downloads model on first use)."""
    global _ranker
    if _ranker is None:
        try:
            from flashrank import Ranker
            from app.core.config import settings
            _ranker = Ranker(model_name=settings.RERANK_MODEL)
            logger.info(f"FlashRank reranker initialized ({settings.RERANK_MODEL})")
        except Exception as e:
            logger.warning(f"FlashRank unavailable, reranking disabled: {e}")
    return _ranker


def rerank(query: str, documents: list[str], top_k: int = 3) -> list[str]:
    """Rerank documents by cross-encoder relevance to query.

    Args:
        query: The search query
        documents: List of document texts from vector search
        top_k: Number of top results to return after reranking

    Returns:
        Reranked list of document texts, best first. Falls back to
        original order if FlashRank is unavailable.
    """
    if not documents:
        return []

    ranker = _get_ranker()
    if ranker is None:
        # Graceful fallback: return original order, truncated
        return documents[:top_k]

    try:
        from flashrank import RerankRequest

        # FlashRank expects list of dicts with "text" key
        passages = [{"text": doc} for doc in documents]
        request = RerankRequest(query=query, passages=passages)
        results = ranker.rerank(request)

        # Results are sorted by score descending
        reranked = [r["text"] for r in results[:top_k]]
        logger.debug(
            f"Reranked {len(documents)} → {len(reranked)} docs "
            f"(top score: {results[0]['score']:.3f})"
        )
        return reranked

    except Exception as e:
        logger.warning(f"Reranking failed, using original order: {e}")
        return documents[:top_k]


def rerank_with_scores(
    query: str, documents: list[str], top_k: int = 3
) -> list[tuple[str, float]]:
    """Like rerank() but returns (text, score) tuples for diagnostics."""
    if not documents:
        return []

    ranker = _get_ranker()
    if ranker is None:
        return [(doc, 0.0) for doc in documents[:top_k]]

    try:
        from flashrank import RerankRequest

        passages = [{"text": doc} for doc in documents]
        request = RerankRequest(query=query, passages=passages)
        results = ranker.rerank(request)

        return [(r["text"], r["score"]) for r in results[:top_k]]

    except Exception as e:
        logger.warning(f"Reranking failed: {e}")
        return [(doc, 0.0) for doc in documents[:top_k]]
