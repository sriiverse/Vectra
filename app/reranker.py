"""
Vectra: Cross-Encoder Reranking Module.

WHY TWO STAGES (bi-encoder + cross-encoder)?
============================================

Stage 1 — CLIP (bi-encoder):
  The bi-encoder independently encodes the query and every document.
  Similarity = dot product of their embeddings.
  Pro: Extremely fast — the document embeddings are pre-computed and stored.
  Con: The model never jointly attends to both query and document during encoding.
       Information that requires comparing the two (e.g., "this shoe has exactly
       the same sole pattern as the query image") is lost.

Stage 2 — Cross-Encoder (this module):
  The cross-encoder takes (query_text, candidate_name_description) as a PAIR
  and outputs a scalar relevance score. The model jointly attends to both during
  inference, catching fine-grained relevance signals the bi-encoder misses.
  Pro: Much higher accuracy than bi-encoder similarity alone.
  Con: Cannot pre-compute scores — requires O(k) inference calls at query time.
       This is why we only rerank the top 50 bi-encoder candidates, not all N
       products in the database.

The two-stage pipeline is the industry standard architecture for large-scale
retrieval systems (used by Google, Bing, Amazon Alexa Shopping, etc.).

RERANKER MODEL CHOICE:
  ms-marco-MiniLM-L-6-v2 is a distilled cross-encoder fine-tuned on MS-MARCO
  passage ranking. It is accurate enough for product name/description reranking
  and runs in ~10ms for 50 candidates on CPU — well within P95 latency budget.
"""

import os
from sentence_transformers import CrossEncoder
from typing import Any

_RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
_reranker: CrossEncoder | None = None
DEFAULT_TOP_N = int(os.getenv("DEFAULT_TOP_N_RERANK", 10))


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        print(f"[Reranker] Loading cross-encoder: {_RERANKER_MODEL}...")
        _reranker = CrossEncoder(_RERANKER_MODEL)
        print("[Reranker] Reranker loaded.")
    return _reranker


def rerank(
    query_text: str,
    candidates: list[dict[str, Any]],
    top_n: int = DEFAULT_TOP_N,
) -> list[dict[str, Any]]:
    """
    Rerank a list of bi-encoder candidates using the cross-encoder.

    The cross-encoder scores each (query_text, product_text) pair jointly.
    Products are sorted by this score descending, and the top_n are returned.

    Args:
        query_text:  The user's text input (modifier or general description).
                     If the user only uploaded an image with no text, we use
                     the product category + top CLIP result name as a fallback
                     query to still benefit from reranking.
        candidates:  List of product dicts from hybrid_search()
        top_n:       Final number of results to return after reranking

    Returns:
        Re-sorted list of product dicts (top_n), each with an added
        'rerank_score' key for transparency/debugging.
    """
    if not candidates:
        return []

    reranker = _get_reranker()

    # Build (query, document) pairs
    # We use name + subcategory + color + description for maximum context
    pairs = []
    for c in candidates:
        doc_text = " ".join(filter(None, [
            c.get("name", ""),
            c.get("subcategory", ""),
            c.get("color", ""),
            c.get("description", ""),
        ]))
        pairs.append((query_text, doc_text))

    scores = reranker.predict(pairs)

    # Attach score to each candidate and sort
    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)

    reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    return reranked[:top_n]
