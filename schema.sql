-- ============================================================
-- Vectra: A Multi-Modal Hybrid Retrieval System
-- Schema: Products table with pgvector support
-- ============================================================

-- Enable the pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Core products table
-- CLIP ViT-B/32 produces 512-dimensional embeddings
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    category        TEXT NOT NULL CHECK (category IN ('Apparel', 'Electronics', 'Home', 'Footwear', 'Beauty')),
    subcategory     TEXT,
    color           TEXT,
    price           NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    in_stock        BOOLEAN NOT NULL DEFAULT TRUE,
    stock_count     INTEGER DEFAULT 0,
    image_path      TEXT,
    description     TEXT,
    image_embedding VECTOR(512),          -- CLIP ViT-B/32 embedding dimension
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- HNSW index for Approximate Nearest Neighbor (ANN) search
-- 
-- Why HNSW over exact KNN?
--   Exact KNN scales as O(n) per query — unusable at 100K+ products.
--   HNSW gives sub-linear search time with tunable accuracy trade-off.
--
-- Parameters:
--   m = 16           : number of bi-directional links per node
--                      Higher = better recall, more memory usage
--   ef_construction  : search width during index build
--   64 is a good default; increase for higher recall at index build cost
--
-- operator class: vector_cosine_ops
--   CLIP embeddings are normalized unit vectors, so cosine similarity
--   is the correct distance metric (equivalent to dot product at unit norm)
-- ============================================================
CREATE INDEX IF NOT EXISTS products_embedding_hnsw_idx
ON products
USING hnsw (image_embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Standard B-tree indexes for SQL filter columns
CREATE INDEX IF NOT EXISTS products_category_idx ON products (category);
CREATE INDEX IF NOT EXISTS products_price_idx ON products (price);
CREATE INDEX IF NOT EXISTS products_in_stock_idx ON products (in_stock);

-- ============================================================
-- GIN index for full-text keyword search (tsvector)
CREATE INDEX IF NOT EXISTS idx_products_fts ON products
USING GIN(to_tsvector('english', COALESCE(name, '') || ' ' || COALESCE(description, '')));

-- Evaluation log table
-- Stores search queries and retrieval metrics for benchmarking
-- ============================================================
CREATE TABLE IF NOT EXISTS search_logs (
    id              SERIAL PRIMARY KEY,
    query_text      TEXT,
    category_filter TEXT,
    max_price       NUMERIC(10, 2),
    result_ids      INTEGER[],
    latency_ms      FLOAT,
    searched_at     TIMESTAMPTZ DEFAULT NOW()
);
