"""
Vectra: Hybrid SQL + pgvector Retrieval Module.

Executes a two-constraint query:
  1. Hard constraint (SQL WHERE): category, price, stock status, color, size range — 
     filters applied BEFORE vector similarity. This guarantees correctness — 
     no out-of-stock, wrong-category, or wrong-size product can appear in results.

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
    # New structured attribute filters
    color: str | None = None,
    size_min: float | None = None,
    size_max: float | None = None,
    subcategory: str | None = None,
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
        color:        If set, restrict to exact color match
        size_min:     If set, exclude products with size_max < size_min
        size_max:     If set, exclude products with size_min > size_max
        subcategory:  If set, restrict to this subcategory

    Returns:
        Tuple of (list of product dicts, query_latency_ms)

    Each product dict contains:
        id, name, category, subcategory, color, price, in_stock,
        image_path, description, size_min, size_max, similarity (cosine similarity score)
    """
    conditions = []
    params: list[Any] = []

    if in_stock_only:
        conditions.append("in_stock = TRUE")

    if category:
        conditions.append("category = %s")
        params.append(category)

    if subcategory:
        conditions.append("subcategory = %s")
        params.append(subcategory)

    if max_price is not None:
        conditions.append("price <= %s")
        params.append(max_price)

    if color:
        conditions.append("color = %s")
        params.append(color)

    if size_min is not None and size_max is not None:
        conditions.append("size_min IS NOT NULL AND size_max IS NOT NULL")
        conditions.append("size_min <= %s AND size_max >= %s")
        params.append(size_max)
        params.append(size_min)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

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
            size_min,
            size_max,
            1 - (image_embedding <=> %s::vector) AS similarity
        FROM products
        {where_clause}
        ORDER BY image_embedding <=> %s::vector
        LIMIT %s;
    """

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


def keyword_search(
    query_text: str,
    category: str | None = None,
    max_price: float | None = None,
    in_stock_only: bool = True,
    top_k: int = DEFAULT_TOP_K,
    color: str | None = None,
    size_min: float | None = None,
    size_max: float | None = None,
    subcategory: str | None = None,
) -> tuple[list[dict[str, Any]], float]:
    conditions = [
        "to_tsvector('english', COALESCE(name, '') || ' ' || COALESCE(description, '')) @@ plainto_tsquery('english', %s)"
    ]
    filter_params: list[Any] = []

    if in_stock_only:
        conditions.append("in_stock = TRUE")

    if category:
        conditions.append("category = %s")
        filter_params.append(category)

    if subcategory:
        conditions.append("subcategory = %s")
        filter_params.append(subcategory)

    if max_price is not None:
        conditions.append("price <= %s")
        filter_params.append(max_price)

    if color:
        conditions.append("color = %s")
        filter_params.append(color)

    if size_min is not None and size_max is not None:
        conditions.append("size_min IS NOT NULL AND size_max IS NOT NULL")
        conditions.append("size_min <= %s AND size_max >= %s")
        filter_params.append(size_max)
        filter_params.append(size_min)

    where_clause = "WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT
            id, name, category, subcategory, color, price,
            in_stock, image_path, description, size_min, size_max,
            ts_rank(to_tsvector('english', COALESCE(name, '') || ' ' || COALESCE(description, '')),
                    plainto_tsquery('english', %s)) AS similarity
        FROM products
        {where_clause}
        ORDER BY similarity DESC
        LIMIT %s;
    """

    params = [query_text] + filter_params + [query_text, top_k]

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
