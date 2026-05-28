"""
Vectra: Evaluation Script — Recall@K, Precision@K, nDCG@K

Evaluates retrieval quality across three pipeline modes:
  keyword    — PostgreSQL full-text search (tsvector) baseline
  clip_only  — CLIP bi-encoder + pgvector ANN, no reranker
  full       — CLIP + cross-encoder reranking (production pipeline)

Usage:
    python scripts/evaluate.py --mode full
    python scripts/evaluate.py --mode clip_only
    python scripts/evaluate.py --mode keyword
    python scripts/evaluate.py --compare          # all three, with comparison table
    python scripts/evaluate.py --top-k 5 --verbose
"""

import sys
import math
import json
import argparse
import requests
from pathlib import Path
from PIL import Image
import io

sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://localhost:8000"

TEST_QUERIES = [
    {
        "name": "Color variation test — white T-shirt",
        "image_name": "product_0001.jpg",
        "text_modifier": None,
        "keyword_query": "white cotton t-shirt",
        "filters": {"category": "Apparel", "in_stock_only": False},
        "relevant_names": ["Classic Cotton T-Shirt"],
        "description": "Should retrieve all 3 T-shirt color variants",
    },
    {
        "name": "Multi-modal modifier — black shoes",
        "image_name": "product_0041.jpg",
        "text_modifier": "but in black",
        "keyword_query": "black shoes",
        "filters": {"category": "Footwear", "in_stock_only": False},
        "relevant_names": ["Running Sneakers"],
        "description": "Text modifier should shift results toward black shoe variants",
    },
    {
        "name": "Price filter correctness",
        "image_name": "product_0041.jpg",
        "text_modifier": None,
        "keyword_query": "affordable shoes under 1500",
        "filters": {"category": "Footwear", "max_price": 1500, "in_stock_only": False},
        "relevant_names": ["Flip Flops", "Canvas Sneakers"],
        "description": "Expensive sneakers (₹2999+) must NOT appear despite visual similarity",
    },
    {
        "name": "In-stock filter correctness",
        "image_name": "product_0001.jpg",
        "text_modifier": None,
        "keyword_query": "cotton t-shirt",
        "filters": {"category": "Apparel", "in_stock_only": True},
        "relevant_names": ["Classic Cotton T-Shirt"],
        "excluded_names": ["Classic Cotton T-Shirt Navy"],
        "description": "Out-of-stock Navy T-shirt must NOT appear",
    },
    {
        "name": "Category boundary — Electronics",
        "image_name": "product_0066.jpg",
        "text_modifier": None,
        "keyword_query": "audio electronics",
        "filters": {"category": "Electronics", "in_stock_only": False},
        "relevant_names": ["Wireless Earbuds", "Bluetooth Speaker", "Noise Cancelling"],
        "description": "Audio electronics should cluster together",
    },
    {
        "name": "Near-duplicate detection",
        "image_name": "product_0096.jpg",
        "text_modifier": None,
        "keyword_query": "ceramic coffee mug",
        "filters": {"category": "Home", "in_stock_only": False},
        "relevant_names": ["Ceramic Coffee Mug"],
        "description": "Should find both mug color variants",
    },
]


def compute_dcg(relevance_scores: list[int]) -> float:
    return sum(
        rel / math.log2(rank + 2)
        for rank, rel in enumerate(relevance_scores)
    )


def compute_ndcg(retrieved: list[str], relevant: list[str], k: int) -> float:
    relevance = [
        1 if any(r.lower() in name.lower() for r in relevant) else 0
        for name in retrieved[:k]
    ]
    dcg = compute_dcg(relevance)
    ideal = [1] * min(len(relevant), k) + [0] * max(0, k - len(relevant))
    idcg = compute_dcg(ideal)
    return dcg / idcg if idcg > 0 else 0.0


def compute_recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    hits = sum(1 for name in retrieved[:k] if any(r.lower() in name.lower() for r in relevant))
    return hits / len(relevant) if relevant else 0.0


def compute_precision_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    hits = sum(1 if any(r.lower() in name.lower() for r in relevant) else 0 for name in retrieved[:k])
    return hits / k


def run_keyword_query(query_text: str, filters: dict, top_k: int) -> list[str] | None:
    try:
        resp = requests.post(
            f"{API_BASE}/search/text",
            data={"query": query_text, "filters": json.dumps(filters)},
            timeout=30,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return [f"{r['name']} {r['color']}" if r.get("color") else r["name"] for r in data["results"]]
    except Exception:
        return None


def run_image_search(image_path: Path, filters: dict, top_k: int) -> list[str] | None:
    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                f"{API_BASE}/search",
                files={"image": (image_path.name, f, "image/jpeg")},
                data={"filters": json.dumps(filters)},
                timeout=30,
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return [f"{r['name']} {r['color']}" if r.get("color") else r["name"] for r in data["results"]]
    except Exception:
        return None


def run_evaluation(mode: str, top_k: int = 10, verbose: bool = False):
    mode_label = {"keyword": "Keyword (BM25)", "clip_only": "CLIP only", "full": "CLIP + reranker"}
    print(f"\n{'='*60}")
    print(f"  Vectra Evaluation — mode={mode_label.get(mode, mode)}  top_k={top_k}")
    print(f"{'='*60}\n")

    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        data = r.json()
        print(f"API: online · {data['products_indexed']} products indexed\n")
    except Exception as e:
        print(f"ERROR: API not reachable — {e}")
        print("Start the server first: uvicorn app.main:app --host 0.0.0.0 --port 8000")
        return

    images_dir = Path("data/synthetic/images")
    all_ndcg, all_recall, all_precision = [], [], []

    for test in TEST_QUERIES:
        if mode == "keyword":
            query = test.get("keyword_query") or test.get("text_modifier") or test["relevant_names"][0]
            filters = {**test.get("filters", {}), "top_n": top_k}
            retrieved_names = run_keyword_query(query, filters, top_k)
            if retrieved_names is None:
                print(f"✗ '{test['name']}' — keyword search failed")
                continue
        else:
            img_path = images_dir / test["image_name"]
            if not img_path.exists():
                print(f"⚠ Skipping '{test['name']}' — image not found: {img_path}")
                continue

            filters = {**test.get("filters", {}), "top_n": top_k}
            if test.get("text_modifier"):
                filters["text_modifier"] = test["text_modifier"]
            if mode == "clip_only":
                filters["skip_rerank"] = True

            retrieved_names = run_image_search(img_path, filters, top_k)
            if retrieved_names is None:
                print(f"✗ '{test['name']}' — search failed")
                continue

        ndcg = compute_ndcg(retrieved_names, test["relevant_names"], top_k)
        recall = compute_recall_at_k(retrieved_names, test["relevant_names"], top_k)
        precis = compute_precision_at_k(retrieved_names, test["relevant_names"], top_k)

        all_ndcg.append(ndcg)
        all_recall.append(recall)
        all_precision.append(precis)

        status = "✓" if ndcg > 0.5 else "⚠"
        print(f"{status} {test['name']}")
        print(f"   nDCG@{top_k}={ndcg:.3f}  Recall@{top_k}={recall:.3f}  P@{top_k}={precis:.3f}")

        if verbose:
            print(f"   Relevant keywords: {test['relevant_names']}")
            print(f"   Top results: {retrieved_names[:5]}")

        if test.get("excluded_names"):
            violations = [
                name for name in retrieved_names
                if any(ex.lower() in name.lower() for ex in test["excluded_names"])
            ]
            if violations:
                print(f"   ✗ FILTER VIOLATION: {violations} should have been excluded!")
            else:
                print(f"   ✓ Filter exclusion: correct")
        print()

    if all_ndcg:
        print(f"{'='*60}")
        print(f"  AGGREGATE RESULTS (n={len(all_ndcg)} test cases)")
        print(f"{'='*60}")
        print(f"  Mean nDCG@{top_k}:      {sum(all_ndcg)/len(all_ndcg):.3f}")
        print(f"  Mean Recall@{top_k}:    {sum(all_recall)/len(all_recall):.3f}")
        print(f"  Mean Precision@{top_k}: {sum(all_precision)/len(all_precision):.3f}")
        print()
        return sum(all_ndcg) / len(all_ndcg), sum(all_recall) / len(all_recall), sum(all_precision) / len(all_precision)

    return 0, 0, 0


def run_comparison(top_k: int = 10):
    modes = [
        ("keyword",   "Keyword (BM25)"),
        ("clip_only", "CLIP only"),
        ("full",      "CLIP + reranker (Vectra)"),
    ]

    results = {}
    for mode_key, mode_label in modes:
        print(f"\n{'#'*60}")
        print(f"#  MODE: {mode_label}")
        print(f"{'#'*60}")
        ndcg, recall, precis = run_evaluation(mode_key, top_k=top_k, verbose=False)
        results[mode_key] = {
            "label": mode_label,
            "ndcg": ndcg,
            "recall": recall,
            "precision": precis,
        }

    print(f"\n{'='*60}")
    print(f"  BASELINE COMPARISON TABLE — top_k={top_k}")
    print(f"{'='*60}")
    print(f"  {'Pipeline':<30} {'nDCG':<8} {'Recall':<8} {'Precision':<8}")
    print(f"  {'─'*30} {'─'*8} {'─'*8} {'─'*8}")
    for r in results.values():
        print(f"  {r['label']:<30} {r['ndcg']:<8.3f} {r['recall']:<8.3f} {r['precision']:<8.3f}")
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vectra evaluation suite")
    parser.add_argument("--top-k", type=int, default=10, help="Evaluation cutoff K")
    parser.add_argument("--verbose", action="store_true", help="Show top results per query")
    parser.add_argument("--mode", choices=["keyword", "clip_only", "full"], default="full",
                        help="Pipeline mode to evaluate")
    parser.add_argument("--compare", action="store_true", help="Run all modes and print comparison table")
    args = parser.parse_args()

    if args.compare:
        run_comparison(top_k=args.top_k)
    else:
        run_evaluation(mode=args.mode, top_k=args.top_k, verbose=args.verbose)
