"""
Vectra: Cross-Encoder Reranking Module with Metadata-Aware Scoring.

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

METADATA-AWARE BLENDING:
  Beyond the cross-encoder, we also compute attribute match bonuses for
  structured fields (color, size, category, subcategory, price). These bonuses
  ensure that a product matching the user's explicit attribute constraints
  ranks higher than a visually similar product that doesn't match.
"""

import os
import math
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


def compute_attribute_match_bonus(
    candidate: dict[str, Any],
    parsed_attrs: dict | None,
) -> float:
    """
    Compute a bonus score based on structured attribute matches.

    Returns a value in [0, 1] representing how well the candidate's
    structured metadata matches the user's parsed attribute filters.
    """
    if not parsed_attrs:
        return 0.0

    bonus = 0.0
    checks = 0

    # Color match
    if parsed_attrs.get("color") and candidate.get("color"):
        if candidate["color"].lower() == parsed_attrs["color"].lower():
            bonus += 1.0
        checks += 1

    # Category match
    if parsed_attrs.get("category") and candidate.get("category"):
        if candidate["category"].lower() == parsed_attrs["category"].lower():
            bonus += 1.0
        checks += 1

    # Subcategory match
    if parsed_attrs.get("subcategory") and candidate.get("subcategory"):
        if candidate["subcategory"].lower() == parsed_attrs["subcategory"].lower():
            bonus += 1.5  # subcategory match is more specific
        checks += 1

    # Size match — check that candidate's size range overlaps the query
    if parsed_attrs.get("size_min") is not None and parsed_attrs.get("size_max") is not None:
        c_min = candidate.get("size_min")
        c_max = candidate.get("size_max")
        if c_min is not None and c_max is not None:
            c_min = float(c_min)
            c_max = float(c_max)
            q_min = float(parsed_attrs["size_min"])
            q_max = float(parsed_attrs["size_max"])
            # Calculate overlap ratio
            overlap = min(c_max, q_max) - max(c_min, q_min)
            size_range = max(c_max - c_min, q_max - q_min, 1.0)
            overlap_ratio = max(0.0, overlap / size_range)
            bonus += 1.0 * overlap_ratio
        checks += 1

    # Price match
    if parsed_attrs.get("max_price") is not None:
        c_price = candidate.get("price")
        if c_price is not None and float(c_price) <= parsed_attrs["max_price"]:
            bonus += 0.5
        checks += 0.5  # partial weight — price under is not a strong positive signal

    return bonus / max(checks, 1)


def rerank(
    query_text: str,
    candidates: list[dict[str, Any]],
    top_n: int = DEFAULT_TOP_N,
    parsed_attrs: dict | None = None,
) -> list[dict[str, Any]]:
    """
    Rerank candidates using cross-encoder + metadata attribute matching.

    The blended score = CLIP similarity 
                        + 0.25 * sigmoid(cross_encoder_score) 
                        + 0.15 * attribute_match_bonus

    Args:
        query_text:   The user's text input (modifier or general description).
        candidates:   List of product dicts from hybrid_search()
        top_n:        Final number of results to return after reranking
        parsed_attrs: Parsed structured attributes from attribute_parser

    Returns:
        Re-sorted list of product dicts (top_n), each with 'rerank_score' and
        'attr_bonus' keys for transparency/debugging.
    """
    if not candidates:
        return []

    reranker = _get_reranker()

    pairs = []
    for c in candidates:
        doc_text = " ".join(filter(None, [
            c.get("name", ""),
            c.get("category", ""),
            c.get("subcategory", ""),
            c.get("color", ""),
            c.get("description", ""),
        ]))
        pairs.append((query_text, doc_text))

    scores = reranker.predict(pairs)

    for candidate, score in zip(candidates, scores):
        candidate["rerank_score"] = float(score)
        ce_sigmoid = 1 / (1 + math.exp(-float(score)))
        attr_bonus = compute_attribute_match_bonus(candidate, parsed_attrs)
        candidate["attr_bonus"] = attr_bonus
        # Blended score: CLIP similarity + reranker signal + metadata match
        candidate["_blended_score"] = candidate["similarity"] + 0.25 * ce_sigmoid + 0.15 * attr_bonus

    reranked = sorted(candidates, key=lambda x: x["_blended_score"], reverse=True)
    return reranked[:top_n]
