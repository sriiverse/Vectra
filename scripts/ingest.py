"""
Vectra: Data Ingestion Pipeline.

Reads product metadata from a CSV file, generates CLIP embeddings for each
product image, and inserts them into PostgreSQL via batched SQL INSERT statements.

Supports both synthetic dataset (Phase 1) and Kaggle dataset (Phase 2+).

Usage:
    python scripts/ingest.py --csv data/synthetic/products.csv
    python scripts/ingest.py --csv data/kaggle/products.csv --batch-size 32
"""

import os
import sys
import csv
import argparse
import numpy as np
from pathlib import Path
from tqdm import tqdm
from PIL import Image

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.embedder import embed_image
from app.database import get_conn, put_conn
from dotenv import load_dotenv

load_dotenv()


def clear_products(conn):
    """Truncate the products table before re-ingestion."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE products RESTART IDENTITY CASCADE;")
    conn.commit()
    print("[Ingest] Products table cleared.")


def ingest_batch(conn, batch: list[dict]):
    """Insert a batch of products with their embeddings into PostgreSQL."""
    with conn.cursor() as cur:
        for product in batch:
            cur.execute(
                """
                INSERT INTO products
                    (name, category, subcategory, color, price, in_stock,
                     stock_count, image_path, description, image_embedding)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """,
                (
                    product["name"],
                    product["category"],
                    product.get("subcategory"),
                    product.get("color"),
                    float(product["price"]),
                    product["in_stock"] in (True, "True", "true", "1"),
                    int(product.get("stock_count", 0)),
                    product.get("image_path"),
                    product.get("description"),
                    product["embedding"],
                )
            )
    conn.commit()


def run_ingestion(csv_path: str, batch_size: int = 16, clear: bool = False):
    print(f"[Ingest] Starting ingestion from: {csv_path}")

    conn = get_conn()

    if clear:
        clear_products(conn)

    with open(csv_path, newline="") as f:
        reader = list(csv.DictReader(f))

    print(f"[Ingest] Found {len(reader)} products to ingest.")

    batch = []
    failed = []

    for row in tqdm(reader, desc="Embedding & inserting"):
        image_path = row.get("image_path", "")

        try:
            img = Image.open(image_path).convert("RGB")
            embedding = embed_image(img)
            # pgvector expects a list, not a numpy array
            row["embedding"] = embedding.tolist()
            batch.append(row)
        except Exception as e:
            print(f"\n[Ingest] ⚠ Failed to embed {image_path}: {e}")
            failed.append(row.get("name", "unknown"))
            continue

        if len(batch) >= batch_size:
            ingest_batch(conn, batch)
            batch = []

    # Insert remaining
    if batch:
        ingest_batch(conn, batch)

    put_conn(conn)

    print(f"\n[Ingest] ✓ Ingestion complete.")
    print(f"  Successfully ingested: {len(reader) - len(failed)} products")
    if failed:
        print(f"  Failed: {len(failed)} products: {failed}")

    # Verify count in DB
    conn2 = get_conn()
    with conn2.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM products;")
        count = cur.fetchone()[0]
    put_conn(conn2)
    print(f"  Total products in database: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vectra ingestion pipeline")
    parser.add_argument("--csv", required=True, help="Path to products CSV file")
    parser.add_argument("--batch-size", type=int, default=16, help="Insert batch size")
    parser.add_argument("--clear", action="store_true", help="Clear existing products before ingestion")
    args = parser.parse_args()

    run_ingestion(args.csv, batch_size=args.batch_size, clear=args.clear)
