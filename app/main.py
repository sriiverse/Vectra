"""
Vectra: FastAPI Application Entry Point.

Endpoints:
    GET  /             → Health check
    GET  /health       → Detailed health + DB connectivity check
    POST /search       → Main multi-modal hybrid search endpoint
    GET  /products     → List all products (for UI catalog display)
    GET  /products/{id} → Single product detail
"""

import io
import os
import json
import time
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image

logger = logging.getLogger("vectra")

from app.database import get_conn, put_conn, close_pool
from app.embedder import embed_multimodal
from app.search import hybrid_search, keyword_search
from app.reranker import rerank
from app.models import SearchResponse, ProductResult, SearchFilters
from app.attribute_parser import parse_attributes


# ---------------------------------------------------------------
# Lifespan: startup & shutdown hooks
# ---------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Warming up models...")
    from app.embedder import _get_model
    from app.reranker import _get_reranker
    _get_model()
    _get_reranker()
    logger.info("Ready.")
    yield
    close_pool()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------
# App init
# ---------------------------------------------------------------
app = FastAPI(
    title="Vectra",
    description="A Multi-Modal Hybrid Retrieval System for E-Commerce Visual Search",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow frontend (served separately or on same origin) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve product images from the data directory
app.mount("/images", StaticFiles(directory="data"), name="images")

# ---------------------------------------------------------------
# Routes
# ---------------------------------------------------------------


@app.get("/health", tags=["System"])
async def health():
    """Check API health and database connectivity."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM products;")
            count = cur.fetchone()[0]
        return {"status": "ok", "products_indexed": count}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB error: {e}")
    finally:
        put_conn(conn)


@app.post("/search", response_model=SearchResponse, tags=["Search"])
async def search(
    image: UploadFile = File(..., description="Product image to search by"),
    filters: str = Form(
        default="{}",
        description="JSON string of SearchFilters (category, max_price, in_stock_only, text_modifier, text_weight, top_n)"
    ),
):
    """
    Multi-modal hybrid search with structured attribute parsing.

    Pipeline:
      1. Parse text modifier into structured attributes (color, size, category, price)
      2. Embed uploaded image (+ optional text modifier) via CLIP
      3. Execute hybrid SQL + pgvector query with structured filters + ANN similarity
      4. Rerank top-K candidates using Cross-Encoder + metadata match bonus
      5. Return top-N results with per-stage scores
    """
    # Parse filters from JSON form field
    try:
        filter_data = json.loads(filters)
        f = SearchFilters(**filter_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid filters JSON: {e}")

    # Read and validate image BEFORE calling parser (don't waste work on bad uploads)
    try:
        contents = await image.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read image: {e}")
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large. Max 10MB.")
    try:
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")

    # Step 0: Parse structured attributes from text modifier
    parsed_attrs = parse_attributes(f.text_modifier)

    # Step 1: Generate multi-modal query embedding (timed)
    t0 = time.perf_counter()
    query_vector = embed_multimodal(
        image=pil_image,
        text_modifier=f.text_modifier,
        text_weight=f.text_weight,
    )
    embed_ms = (time.perf_counter() - t0) * 1000

    # Step 2: Hybrid retrieval (SQL structured filters + pgvector ANN, timed separately)
    candidates, retrieval_ms = hybrid_search(
        query_vector=query_vector,
        category=f.category or parsed_attrs.get("category"),
        max_price=f.max_price or parsed_attrs.get("max_price"),
        in_stock_only=f.in_stock_only,
        top_k=int(os.getenv("DEFAULT_TOP_K_RETRIEVAL", 50)),
        color=parsed_attrs.get("color"),
        size_min=parsed_attrs.get("size_min"),
        size_max=parsed_attrs.get("size_max"),
        subcategory=parsed_attrs.get("subcategory"),
    )

    total_retrieved = len(candidates)

    # Record pre-rerank order (by similarity) so frontend can show rank delta
    for i, c in enumerate(candidates):
        c["_pre_rerank_rank"] = i + 1

    # Step 3: Cross-encoder reranking with metadata-aware blending (timed)
    t1 = time.perf_counter()
    if f.skip_rerank:
        for c in candidates:
            c["rerank_score"] = None
            c["attr_bonus"] = None
        reranked = candidates[:f.top_n]
    elif f.text_modifier and f.text_modifier.strip():
        rerank_query = f.text_modifier
        reranked = rerank(
            query_text=rerank_query,
            candidates=candidates,
            top_n=f.top_n,
            parsed_attrs=parsed_attrs,
        )
    else:
        for c in candidates:
            c["rerank_score"] = None
            c["attr_bonus"] = None
            c["_pre_rerank_rank"] = c.get("_pre_rerank_rank", 0)
        reranked = candidates[:f.top_n]
    rerank_ms = (time.perf_counter() - t1) * 1000

    # Annotate each result with final rank and rank delta
    for final_rank, r in enumerate(reranked, start=1):
        pre = r.get("_pre_rerank_rank", final_rank)
        r["rank_delta"] = pre - final_rank   # positive = moved up
        r["pre_rerank_rank"] = pre

    # Log debug info
    logger.info("Modifier='%s' embed=%.1fms retrieval=%.1fms rerank=%.1fms color=%s size=%s-%s cat=%s sub=%s price<=%s",
                f.text_modifier, embed_ms, retrieval_ms, rerank_ms,
                parsed_attrs.get('color'), parsed_attrs.get('size_min'), parsed_attrs.get('size_max'),
                parsed_attrs.get('category'), parsed_attrs.get('subcategory'), parsed_attrs.get('max_price'))

    return SearchResponse(
        results=[ProductResult(**r) for r in reranked],
        total_retrieved=total_retrieved,
        total_returned=len(reranked),
        embed_ms=round(embed_ms, 1),
        retrieval_ms=round(retrieval_ms, 1),
        rerank_ms=round(rerank_ms, 1),
        filters_applied={
            **filter_data,
            "_parsed_attributes": parsed_attrs,
        },
    )


@app.get("/products", tags=["Products"])
async def list_products(
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
) -> dict[str, Any]:
    """List products for the UI catalog view."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if category:
                cur.execute(
                    "SELECT id, name, category, subcategory, color, price, in_stock, image_path "
                    "FROM products WHERE category = %s ORDER BY id LIMIT %s OFFSET %s",
                    (category, limit, offset),
                )
            else:
                cur.execute(
                    "SELECT id, name, category, subcategory, color, price, in_stock, image_path "
                    "FROM products ORDER BY id LIMIT %s OFFSET %s",
                    (limit, offset),
                )
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            products = [dict(zip(cols, row)) for row in rows]

            cur.execute("SELECT COUNT(*) FROM products")
            total = cur.fetchone()[0]

        return {"products": products, "total": total, "limit": limit, "offset": offset}
    finally:
        put_conn(conn)


@app.get("/products/{product_id}", tags=["Products"])
async def get_product(product_id: int) -> dict[str, Any]:
    """Get a single product by ID."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, category, subcategory, color, price, in_stock, image_path, description "
                "FROM products WHERE id = %s",
                (product_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Product not found")
            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))
    finally:
        put_conn(conn)


@app.post("/search/text", tags=["Search"])
async def search_text(
    query: str = Form(..., description="Text query for keyword search"),
    filters: str = Form(default="{}", description="JSON string of SearchFilters"),
):
    """
    Text-only keyword search using PostgreSQL full-text search (tsvector/tsquery).
    Used as a baseline comparison for the multi-modal pipeline.

    Pipeline:
      1. Parse text modifier into structured attributes
      2. Execute PostgreSQL full-text search + structured SQL filters
      3. Return top-N results by ts_rank
    """
    try:
        filter_data = json.loads(filters)
        f = SearchFilters(**filter_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid filters JSON: {e}")

    parsed_attrs = parse_attributes(f.text_modifier or query)

    candidates, retrieval_ms = keyword_search(
        query_text=query,
        category=f.category or parsed_attrs.get("category"),
        max_price=f.max_price or parsed_attrs.get("max_price"),
        in_stock_only=f.in_stock_only,
        top_k=int(os.getenv("DEFAULT_TOP_K_RETRIEVAL", 50)),
        color=parsed_attrs.get("color"),
        size_min=parsed_attrs.get("size_min"),
        size_max=parsed_attrs.get("size_max"),
        subcategory=parsed_attrs.get("subcategory"),
    )

    for i, c in enumerate(candidates):
        c["rerank_score"] = None
        c["attr_bonus"] = None
        c["rank_delta"] = 0
        c["pre_rerank_rank"] = i + 1

    top_n = f.top_n
    results = candidates[:top_n]

    return SearchResponse(
        results=[ProductResult(**r) for r in results],
        total_retrieved=len(candidates),
        total_returned=len(results),
        embed_ms=0.0,
        retrieval_ms=round(retrieval_ms, 1),
        rerank_ms=0.0,
        filters_applied={**filter_data, "_parsed_attributes": parsed_attrs, "_mode": "keyword"},
    )


@app.get("/search/explain", tags=["Search"])
async def explain_search():
    """
    Return the current search pipeline configuration and available attributes.
    Useful for the pipeline inspector UI feature.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM products")
            total = cur.fetchone()[0]
            cur.execute("SELECT DISTINCT category FROM products ORDER BY category")
            categories = [r[0] for r in cur.fetchall()]
            cur.execute("SELECT DISTINCT color FROM products WHERE color IS NOT NULL ORDER BY color")
            colors = [r[0] for r in cur.fetchall()]
    finally:
        put_conn(conn)

    return {
        "pipeline": {
            "stage1": "CLIP bi-encoder (image + optional text embedding)",
            "stage2": "SQL structured attribute filters (color, size, category, price)",
            "stage3": f"pgvector HNSW ANN search (top-{os.getenv('DEFAULT_TOP_K_RETRIEVAL', '50')})",
            "stage4": f"Cross-encoder reranking with metadata bonus (top-{os.getenv('DEFAULT_TOP_N_RERANK', '10')})",
        },
        "database": {
            "total_products": total,
            "categories": categories,
            "colors": colors,
        },
        "attribute_parser": {
            "description": "Extracts structured filters from natural language text",
            "supported": ["color", "size range", "category hint", "subcategory hint", "max price"],
        },
        "scoring": {
            "similarity": "CLIP cosine similarity (0-1)",
            "rerank_score": "Cross-encoder relevance logit",
            "attr_bonus": "Attribute match bonus (0-1)",
            "blended_score": "similarity + 0.25*sigmoid(rerank_score) + 0.15*attr_bonus",
        },
    }


# Serve frontend at root
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
