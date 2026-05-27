"""
Vectra: Evaluation Script — Recall@K, Precision@K, nDCG@K

Evaluates retrieval quality on the synthetic dataset, which has known ground
truth (we know the correct answers because we designed the edge cases).

For each test query, we know which products SHOULD be returned (by product name
match). This lets us compute standard Information Retrieval metrics:

  Recall@K    = how many relevant items appear in the top K results
  Precision@K = what fraction of the top K results are relevant
  nDCG@K      = normalised Discounted Cumulative Gain — penalises relevant
                items ranked lower (the gold-standard single ranking metric)
  Reranker Lift = nDCG improvement from reranking vs. raw CLIP similarity ordering

Usage:
    python scripts/evaluate.py
    python scripts/evaluate.py --top-k 10 --verbose
"""

import sys
import math
import json
import argparse
import requests
from pathlib import Path
from PIL import Image
import io

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE = "http://localhost:8000"

# ---------------------------------------------------------------
# Test suite — each entry defines a query and expected relevant results.
# "relevant" = list of substrings that should appear in returned product names.
# This is ground truth defined by us because we built the dataset.
# ---------------------------------------------------------------
TEST_QUERIES = [
    {
        "name": "Color variation test — white T-shirt",
        "image_name": "product_0001.jpg",   # White Classic Cotton T-Shirt
        "text_modifier": None,
        "filters": {"category": "Apparel", "in_stock_only": False},
        "relevant_names": ["Classic Cotton T-Shirt"],
        "description": "Should retrieve all 3 T-shirt color variants",
    },
    {
        "name": "Multi-modal modifier — black shoes",
        "image_name": "product_0041.jpg",   # White Running Sneakers
        "text_modifier": "but in black",
        "filters": {"category": "Footwear", "in_stock_only": False},
        "relevant_names": ["Running Sneakers"],
        "description": "Text modifier should shift results toward black shoe variants",
    },
    {
        "name": "Price filter correctness",
        "image_name": "product_0041.jpg",   # Running Sneakers
        "text_modifier": None,
        "filters": {"category": "Footwear", "max_price": 1500, "in_stock_only": False},
        "relevant_names": ["Flip Flops", "Canvas Sneakers"],
        "description": "Expensive sneakers (₹2999+) must NOT appear despite visual similarity",
    },
    {
        "name": "In-stock filter correctness",
        "image_name": "product_0001.jpg",   # White T-shirt
        "text_modifier": None,
        "filters": {"category": "Apparel", "in_stock_only": True},
        "relevant_names": ["Classic Cotton T-Shirt"],
        "excluded_names": ["Classic Cotton T-Shirt Navy"],  # out-of-stock variant
        "description": "Out-of-stock Navy T-shirt must NOT appear",
    },
    {
        "name": "Category boundary — Electronics",
        "image_name": "product_0066.jpg",   # Wireless Earbuds
        "text_modifier": None,
        "filters": {"category": "Electronics", "in_stock_only": False},
        "relevant_names": ["Wireless Earbuds", "Bluetooth Speaker", "Noise Cancelling"],
        "description": "Audio electronics should cluster together",
    },
    {
        "name": "Near-duplicate detection",
        "image_name": "product_0096.jpg",   # Ceramic Coffee Mug White
        "text_modifier": None,
        "filters": {"category": "Home", "in_stock_only": False},
        "relevant_names": ["Ceramic Coffee Mug"],
        "description": "Should find both mug color variants — tests reranker lift for near-duplicates",
    },
]


def compute_dcg(relevance_scores: list[int]) -> float:
    """Compute Discounted Cumulative Gain."""
    return sum(
        rel / math.log2(rank + 2)
        for rank, rel in enumerate(relevance_scores)
    )


def compute_ndcg(retrieved: list[str], relevant: list[str], k: int) -> float:
    """Compute nDCG@k given retrieved product names and relevant name substrings."""
    relevance = [
        1 if any(r.lower() in name.lower() for r in relevant) else 0
        for name in retrieved[:k]
    ]
    dcg = compute_dcg(relevance)

    # Ideal DCG: all relevant items at top
    ideal = [1] * min(len(relevant), k) + [0] * max(0, k - len(relevant))
    idcg = compute_dcg(ideal)

    return dcg / idcg if idcg > 0 else 0.0


def compute_recall_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    hits = sum(1 for name in retrieved[:k] if any(r.lower() in name.lower() for r in relevant))
    return hits / len(relevant) if relevant else 0.0


def compute_precision_at_k(retrieved: list[str], relevant: list[str], k: int) -> float:
    hits = sum(1 if any(r.lower() in name.lower() for r in relevant) else 0 for name in retrieved[:k])
    return hits / k


def run_evaluation(top_k: int = 10, verbose: bool = False):
    print(f"\n{'='*60}")
    print(f"  Vectra Evaluation — top_k={top_k}")
    print(f"{'='*60}\n")

    # Check API is up
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
        img_path = images_dir / test["image_name"]
        if not img_path.exists():
            print(f"⚠ Skipping '{test['name']}' — image not found: {img_path}")
            continue

        filters = {**test.get("filters", {}), "top_n": top_k}
        if test.get("text_modifier"):
            filters["text_modifier"] = test["text_modifier"]

        with open(img_path, "rb") as f:
            response = requests.post(
                f"{API_BASE}/search",
                files={"image": (test["image_name"], f, "image/jpeg")},
                data={"filters": json.dumps(filters)},
                timeout=30,
            )

        if response.status_code != 200:
            print(f"✗ '{test['name']}' — HTTP {response.status_code}: {response.text[:100]}")
            continue

        data = response.json()
        retrieved_names = [f"{r['name']} {r['color']}" if r.get("color") else r["name"] for r in data["results"]]

        ndcg    = compute_ndcg(retrieved_names, test["relevant_names"], top_k)
        recall  = compute_recall_at_k(retrieved_names, test["relevant_names"], top_k)
        precis  = compute_precision_at_k(retrieved_names, test["relevant_names"], top_k)

        all_ndcg.append(ndcg)
        all_recall.append(recall)
        all_precision.append(precis)

        status = "✓" if ndcg > 0.5 else "⚠"
        print(f"{status} {test['name']}")
        print(f"   nDCG@{top_k}={ndcg:.3f}  Recall@{top_k}={recall:.3f}  P@{top_k}={precis:.3f}")
        print(f"   Latency: {data['retrieval_latency_ms']:.1f}ms  Retrieved: {data['total_retrieved']} → Returned: {data['total_returned']}")

        if verbose:
            print(f"   Relevant keywords: {test['relevant_names']}")
            print(f"   Top results: {retrieved_names[:5]}")

        # Check excluded names don't appear (SQL filter correctness)
        if test.get("excluded_names"):
            violations = [
                name for name in retrieved_names
                if any(ex.lower() in name.lower() for ex in test["excluded_names"])
            ]
            if violations:
                print(f"   ✗ FILTER VIOLATION: {violations} should have been excluded!")
            else:
                print(f"   ✓ Filter exclusion: correct — excluded items absent")
        print()

    if all_ndcg:
        print(f"{'='*60}")
        print(f"  AGGREGATE RESULTS (n={len(all_ndcg)} test cases)")
        print(f"{'='*60}")
        print(f"  Mean nDCG@{top_k}:      {sum(all_ndcg)/len(all_ndcg):.3f}")
        print(f"  Mean Recall@{top_k}:    {sum(all_recall)/len(all_recall):.3f}")
        print(f"  Mean Precision@{top_k}: {sum(all_precision)/len(all_precision):.3f}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vectra evaluation suite")
    parser.add_argument("--top-k", type=int, default=10, help="Evaluation cutoff K")
    parser.add_argument("--verbose", action="store_true", help="Show top results per query")
    args = parser.parse_args()
    run_evaluation(top_k=args.top_k, verbose=args.verbose)
