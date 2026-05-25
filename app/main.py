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
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image

from app.database import get_conn, put_conn, close_pool
from app.embedder import embed_multimodal
from app.search import hybrid_search
from app.reranker import rerank
from app.models import SearchResponse, ProductResult, SearchFilters


# ---------------------------------------------------------------
# Lifespan: startup & shutdown hooks
# ---------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up models on startup so the first request isn't slow
    print("[Vectra] Warming up models...")
    from app.embedder import _get_model
    from app.reranker import _get_reranker
    _get_model()
    _get_reranker()
    print("[Vectra] Ready.")
    yield
    close_pool()
    print("[Vectra] Shutdown complete.")


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
    Multi-modal hybrid search.

    Pipeline:
      1. Embed uploaded image (+ optional text modifier) via CLIP
      2. Execute hybrid SQL + pgvector query (hard filters + ANN similarity)
      3. Rerank top-50 candidates using Cross-Encoder
      4. Return top-N results with similarity and rerank scores
    """
    # Parse filters from JSON form field
    try:
        filter_data = json.loads(filters)
        f = SearchFilters(**filter_data)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid filters JSON: {e}")

    # Read and decode uploaded image
    try:
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image file: {e}")

    # Step 1: Generate multi-modal query embedding
    query_vector = embed_multimodal(
        image=pil_image,
        text_modifier=f.text_modifier,
        text_weight=f.text_weight,
    )

    # Step 2: Hybrid retrieval (SQL hard filters + pgvector ANN)
    candidates, latency_ms = hybrid_search(
        query_vector=query_vector,
        category=f.category,
        max_price=f.max_price,
        in_stock_only=f.in_stock_only,
        top_k=int(os.getenv("DEFAULT_TOP_K_RETRIEVAL", 50)),
    )

    total_retrieved = len(candidates)

    # Step 3: Cross-encoder reranking
    # Build a query string for the reranker from modifiers + category
    rerank_query = " ".join(filter(None, [
        f.text_modifier,
        f"category: {f.category}" if f.category else None,
        "product image search",
    ])) or "visual product search"

    reranked = rerank(
        query_text=rerank_query,
        candidates=candidates,
        top_n=f.top_n,
    )

    return SearchResponse(
        results=[ProductResult(**r) for r in reranked],
        total_retrieved=total_retrieved,
        total_returned=len(reranked),
        retrieval_latency_ms=latency_ms,
        filters_applied=filter_data,
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


# Serve frontend at root
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
