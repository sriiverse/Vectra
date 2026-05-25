"""
Vectra: Hybrid SQL + pgvector Retrieval Module.

Executes a two-constraint query:
  1. Hard constraint (SQL WHERE): category, price, stock status — filters applied
     BEFORE vector similarity. This guarantees correctness — no out-of-stock or
     wrong-category product can ever appear in results.

  2. Soft constraint (pgvector ANN): cosine distance ordering using the HNSW
     index. Returns the top-k most visually similar candidates that passed the
     hard constraints.

Why hard constraints BEFORE vector sort?
  Pure ANN search on the full index returns globally similar items, then we'd
  have to post-filter — risking that top-k results all get filtered out, forcing
  awkward fallback logic. Pre-filtering in the WHERE clause is cleaner and
  guarantees the SQL planner uses our B-tree indexes on (category, price, in_stock)
  to reduce the candidate set before the HNSW scan.

  Trade-off: Pre-filtering reduces ANN accuracy slightly because the HNSW graph
  was built on all embeddings, not just the filtered subset. For most filter
  selectivities this is acceptable. At very high selectivity (< 0.1% of products),
  partition-level indexes or filtered HNSW should be considered.
"""

import os
import time
import numpy as np
import psycopg2.extras
from typing import Any
from app.database import get_conn, put_conn

DEFAULT_TOP_K = int(os.getenv("DEFAULT_TOP_K_RETRIEVAL", 50))


def hybrid_search(
    query_vector: np.ndarray,
    category: str | None = None,
    max_price: float | None = None,
    in_stock_only: bool = True,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[list[dict[str, Any]], float]:
    """
    Execute a hybrid retrieval query combining SQL hard filters with
    pgvector cosine similarity ordering.

    Args:
        query_vector: L2-normalised 512-dim CLIP embedding
        category:     If set, restrict to this product category
        max_price:    If set, restrict to products at or below this price
        in_stock_only: Whether to restrict to in-stock products only
        top_k:        Number of candidates to return (before reranking)

    Returns:
        Tuple of (list of product dicts, query_latency_ms)

    Each product dict contains:
        id, name, category, subcategory, color, price, in_stock,
        image_path, description, similarity (cosine similarity score)
    """
    # Build WHERE clause dynamically based on provided filters
    conditions = []
    params: list[Any] = []

    if in_stock_only:
        conditions.append("in_stock = TRUE")

    if category:
        conditions.append("category = %s")
        params.append(category)

    if max_price is not None:
        conditions.append("price <= %s")
        params.append(max_price)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    # pgvector cosine distance operator: <=>
    # Returns distance (0 = identical, 2 = opposite); we convert to similarity
    # by: similarity = 1 - cosine_distance
    sql = f"""
        SELECT
            id,
            name,
            category,
            subcategory,
            color,
            price,
            in_stock,
            image_path,
            description,
            1 - (image_embedding <=> %s::vector) AS similarity
        FROM products
        {where_clause}
        ORDER BY image_embedding <=> %s::vector
        LIMIT %s;
    """

    # pgvector expects the vector as a Python list (it handles serialisation)
    vector_param = query_vector.tolist()
    params = [vector_param] + params + [vector_param, top_k]

    conn = get_conn()
    start = time.perf_counter()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        latency_ms = (time.perf_counter() - start) * 1000
        return [dict(row) for row in rows], latency_ms
    finally:
        put_conn(conn)
