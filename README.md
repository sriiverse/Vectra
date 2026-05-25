# Vectra: A Multi-Modal Hybrid Retrieval System

> Find products by image, refined by language. A production-grade AI search engine combining CLIP embeddings, PostgreSQL + pgvector, and cross-encoder reranking.

---

## What it does

Vectra lets you upload any product photo and optionally add a text modifier (e.g. *"but in black"*). It finds visually similar products while respecting hard business constraints — category, price, stock status — applied as SQL `WHERE` clauses **before** the vector search.

This is the same two-stage retrieval architecture used in production at Google, Amazon, and Bing.

---

## Architecture

```
User Input (image + optional text + business filters)
         │
         ▼
[1] Multi-Modal Embedding (CLIP ViT-B/32)
         │  image_emb + 0.3 × text_emb → query_vector (512-dim, L2-normalised)
         ▼
[2] Hybrid SQL + ANN Retrieval (PostgreSQL + pgvector + HNSW)
         │  SQL WHERE filters → cosine ANN search on HNSW index → top 50 candidates
         ▼
[3] Cross-Encoder Reranking (ms-marco-MiniLM-L6)
         │  Joint (query, product) scoring → top N final results
         ▼
[4] FastAPI Response + Frontend UI
```

### Why each design decision was made

| Decision | Rationale |
|---|---|
| CLIP for multi-modal fusion | Contrastive pre-training aligns image + text in a shared embedding space, making linear combination geometrically valid |
| Text weight = 0.3 | Image intent is primary; text refines. 0.3 contributes ~23% of final vector direction. Tunable via `.env` |
| SQL filters BEFORE ANN | Guarantees correctness — out-of-stock/wrong-category products can never appear. Pure post-filtering risks top-K all being filtered out |
| HNSW index | Sub-linear search time vs O(n) exact KNN. Trades tiny accuracy loss for massive speed gain at scale |
| Two-stage retrieval | Bi-encoder (CLIP) is fast but coarse; Cross-Encoder is accurate but slow. Running CE on only 50 pre-filtered candidates gives best of both |
| `pgvector` over a dedicated vector DB | PostgreSQL handles relational business data AND vector similarity in a single system — no dual-write, no consistency issues |

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Model | CLIP `ViT-B/32` (sentence-transformers) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Database | PostgreSQL 15 + `pgvector` extension |
| ANN Index | HNSW (`m=16, ef_construction=64`, cosine ops) |
| Backend | FastAPI + uvicorn |
| Frontend | Vanilla HTML/CSS/JS (zero dependencies) |
| Dataset | Synthetic (66 products, Week 1) → Kaggle Fashion (44K, Week 3) |

---

## Project Structure

```
Vectra/
├── app/
│   ├── main.py          # FastAPI app — /search, /products, /health
│   ├── embedder.py      # CLIP multi-modal embedding (image + text fusion)
│   ├── search.py        # Hybrid SQL + pgvector retrieval
│   ├── reranker.py      # Cross-encoder two-stage reranker
│   ├── models.py        # Pydantic request/response schemas
│   └── database.py      # PostgreSQL connection pool
├── scripts/
│   ├── generate_synthetic.py  # Synthetic dataset generator (edge cases)
│   ├── ingest.py              # CLIP embedding + batched DB ingestion
│   └── evaluate.py            # Recall@K, nDCG@K evaluation suite
├── frontend/
│   ├── index.html       # UI — drag-drop search + catalog + architecture
│   ├── style.css        # Design system
│   └── app.js           # API integration + state management
├── data/
│   └── synthetic/       # 66-product regression test dataset
├── docker-compose.yml   # PostgreSQL + pgvector container
├── schema.sql           # Products table + HNSW index definition
├── requirements.txt
└── .env                 # Config (DB credentials, model names, weights)
```

---

## Quickstart

### 1. Prerequisites
- Docker + Docker Compose
- Python 3.11+

### 2. Start the database
```bash
docker compose up -d
```
This starts PostgreSQL with pgvector and auto-applies `schema.sql`.

### 3. Install Python dependencies
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Generate and ingest the synthetic dataset
```bash
# Generate 66 synthetic products with edge-case images
python scripts/generate_synthetic.py

# Embed with CLIP and insert into PostgreSQL
# (Downloads ~605MB CLIP model on first run — cached after that)
python scripts/ingest.py --csv data/synthetic/products.csv --clear
```

### 5. Start the API server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Open the UI
Navigate to [http://localhost:8000](http://localhost:8000) in your browser.

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | API health + products indexed count |
| `/search` | POST | Multi-modal hybrid search (image + filters) |
| `/products` | GET | List all products (with pagination + category filter) |
| `/products/{id}` | GET | Single product detail |

Interactive Swagger docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Search request example (curl)
```bash
curl -X POST http://localhost:8000/search \
  -F "image=@my_shoe.jpg" \
  -F 'filters={"category":"Footwear","max_price":3000,"in_stock_only":true,"text_modifier":"but in black","top_n":10}'
```

---

## Evaluation

Run the evaluation suite against the synthetic regression dataset:
```bash
python scripts/evaluate.py --top-k 10 --verbose
```

**Metrics reported:**
- `nDCG@10` — primary ranking quality metric
- `Recall@10` — coverage of relevant items
- `Precision@10` — fraction of returned items that are relevant
- Filter violation checks — confirms SQL filters are applied correctly
- Per-query retrieval latency

---

## Dataset Strategy (Progressive Scaling)

| Phase | Dataset | Purpose |
|---|---|---|
| Week 1 | Synthetic 66 products (this) | Validate architecture, debug freely, build permanent regression test set |
| Week 2 | 5K Kaggle Fashion subset | Stress-test HNSW, benchmark P95 latency, real-world noise |
| Week 3+ | Full 44K Kaggle dataset | Tune ANN params, measure reranker lift, prove production scale |

To ingest Kaggle data:
```bash
# Download kaggle dataset to data/kaggle/
python scripts/ingest.py --csv data/kaggle/products.csv --batch-size 32
```

---

## Scalability Notes

Current architecture handles ~100K products comfortably. Documented upgrade path:

- **HNSW** (already in place) — good to ~1M vectors
- **FAISS IVF** — for 10M+ vectors, partition-level indexing
- **Async inference** — batched GPU embedding for high throughput
- **Redis caching** — cache embeddings for repeat queries
- **Read replicas** — scale PostgreSQL reads horizontally

---

## Skills demonstrated

- **AI Engineering:** Foundation model usage (CLIP), two-stage retrieval systems, cross-encoder reranking
- **SQL / Relational DB:** Schema design, complex hybrid queries, pgvector operators (`<=>`), HNSW indexing
- **Python Backend:** FastAPI, async lifespan management, connection pooling, Pydantic v2
- **Systems Thinking:** Pre-filter correctness guarantees, ANN vs exact KNN trade-offs, scalability design

---

*Vectra is a portfolio project demonstrating production-grade AI search engineering.*
