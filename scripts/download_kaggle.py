"""
Vectra: Kaggle Dataset Downloader & Preprocessor
=================================================
Downloads the 'Fashion Product Images (Small)' dataset from Kaggle,
normalises its schema to match Vectra's products table, and writes
a ready-to-ingest CSV at data/kaggle/products.csv.

Prerequisites
-------------
  pip install kaggle
  Place your Kaggle API key at ~/.kaggle/kaggle.json
  (Download from https://www.kaggle.com/settings → API → Create New Token)

Usage
-----
  # Download + preprocess first 5 000 products (Phase 2)
  python scripts/download_kaggle.py --limit 5000

  # Full dataset (~44K) — Phase 3
  python scripts/download_kaggle.py

Column mapping (Kaggle → Vectra)
---------------------------------
  id              → (dropped, DB auto-increments)
  productDisplayName → name
  masterCategory  → category      (mapped to Vectra categories)
  subCategory     → subcategory
  baseColour      → color
  price           → price         (set from articleType mock if absent)
  year / season   → description
  link            → (dropped)
  image file      → image_path    → data/kaggle/images/<id>.jpg
"""

import os
import sys
import csv
import json
import random
import argparse
import zipfile
import shutil
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR     = PROJECT_ROOT / "data" / "kaggle"
IMAGES_DIR   = DATA_DIR / "images"
OUTPUT_CSV   = DATA_DIR / "products.csv"
RAW_ZIP_DIR  = DATA_DIR / "raw"

# ── Kaggle Dataset Identifier ────────────────────────────────────────────────
KAGGLE_DATASET = "paramaggarwal/fashion-product-images-small"

# ── Category Mapping: Kaggle masterCategory → Vectra categories ───────────────
CATEGORY_MAP = {
    "Apparel":     "Apparel",
    "Footwear":    "Footwear",
    "Accessories": "Apparel",       # Closest Vectra match
    "Personal Care": "Beauty",
    "Free Items":  "Home",
    "Sporting Goods": "Apparel",
    "Home":        "Home",
    "Electronics": "Electronics",
}

# ── Realistic price ranges per category (₹) ───────────────────────────────────
PRICE_RANGES = {
    "Apparel":     (299,  4999),
    "Footwear":    (499,  6999),
    "Electronics": (999, 24999),
    "Home":        (199,  8999),
    "Beauty":      (99,   2999),
}


def download_dataset():
    """Use the Kaggle CLI to download the dataset zip."""
    try:
        import kaggle  # noqa — just checking it's importable
    except ImportError:
        print("[Download] Installing kaggle package...")
        os.system(f"{sys.executable} -m pip install -q kaggle")

    print(f"[Download] Fetching '{KAGGLE_DATASET}' from Kaggle...")
    RAW_ZIP_DIR.mkdir(parents=True, exist_ok=True)

    ret = os.system(
        f"kaggle datasets download -d {KAGGLE_DATASET} "
        f"--path {RAW_ZIP_DIR} --unzip"
    )
    if ret != 0:
        print("\n[Download] ✗ Kaggle download failed. Possible causes:")
        print("  1. kaggle.json not found at ~/.kaggle/kaggle.json")
        print("  2. You have not accepted the dataset terms on Kaggle.com")
        print("  3. No internet access")
        sys.exit(1)

    print("[Download] ✓ Dataset downloaded and unzipped.")


def find_styles_csv() -> Path:
    """Locate styles.csv inside the unzipped directory."""
    for candidate in RAW_ZIP_DIR.rglob("styles.csv"):
        return candidate
    # fallback: look for any CSV
    for candidate in RAW_ZIP_DIR.rglob("*.csv"):
        print(f"[Preprocess] Using CSV: {candidate}")
        return candidate
    raise FileNotFoundError(
        f"Could not find styles.csv under {RAW_ZIP_DIR}. "
        "Check the downloaded contents."
    )


def find_images_source() -> Path:
    """Locate the images folder inside the unzipped directory."""
    for candidate in RAW_ZIP_DIR.rglob("images"):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(
        f"Could not find an images/ directory under {RAW_ZIP_DIR}."
    )


def assign_price(category: str, product_name: str) -> float:
    """Assign a realistic price based on category (Kaggle CSV has no prices)."""
    low, high = PRICE_RANGES.get(category, (199, 4999))
    # Deterministic via name hash so re-runs are stable
    seed = sum(ord(c) for c in product_name)
    rng  = random.Random(seed)
    # Round to nearest 99 (e.g. ₹1 499, ₹2 999 — common Indian e-commerce pattern)
    raw = rng.randint(low, high)
    return float((raw // 100) * 100 + 99)


def preprocess(styles_csv: Path, images_src: Path, limit: int | None):
    """Read styles.csv, copy images, and write Vectra-compatible products.csv."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[Preprocess] Reading {styles_csv} ...")
    with open(styles_csv, encoding="utf-8", errors="replace") as f:
        reader = list(csv.DictReader(f))

    print(f"[Preprocess] Total rows in Kaggle CSV: {len(reader)}")

    output_rows  = []
    skipped      = 0
    images_found = 0

    for row in reader:
        # ── Locate the product image ────────────────────────────────────────
        article_id = row.get("id", "").strip()
        img_src    = images_src / f"{article_id}.jpg"

        if not img_src.exists():
            skipped += 1
            continue        # skip products with no image

        # ── Normalise category ───────────────────────────────────────────────
        master_cat   = row.get("masterCategory", "").strip()
        vectra_cat   = CATEGORY_MAP.get(master_cat, "Apparel")

        name         = row.get("productDisplayName", "").strip() or f"Product {article_id}"
        subcategory  = row.get("subCategory", "").strip() or None
        color        = row.get("baseColour", "").strip() or None
        price        = assign_price(vectra_cat, name)

        # Simple in-stock logic: ~85 % in stock (deterministic per id)
        in_stock     = (int(article_id or 0) % 100) < 85

        # Build a short description from available metadata
        year         = row.get("year", "").strip()
        season       = row.get("season", "").strip()
        article_type = row.get("articleType", "").strip()
        desc_parts   = [p for p in [article_type, season, year] if p]
        description  = " · ".join(desc_parts) if desc_parts else None

        # ── Copy image to data/kaggle/images/ ──────────────────────────────
        img_dest = IMAGES_DIR / f"{article_id}.jpg"
        if not img_dest.exists():
            shutil.copy2(img_src, img_dest)
        images_found += 1

        output_rows.append({
            "name":        name,
            "category":    vectra_cat,
            "subcategory": subcategory or "",
            "color":       color or "",
            "price":       price,
            "in_stock":    in_stock,
            "stock_count": random.randint(1, 50) if in_stock else 0,
            "image_path":  str(img_dest.relative_to(PROJECT_ROOT)),
            "description": description or "",
        })

        if limit and len(output_rows) >= limit:
            break

    print(f"[Preprocess] Images found / copied: {images_found}")
    print(f"[Preprocess] Rows skipped (no image): {skipped}")
    print(f"[Preprocess] Output rows: {len(output_rows)}")

    # ── Write output CSV ─────────────────────────────────────────────────────
    fieldnames = ["name", "category", "subcategory", "color",
                  "price", "in_stock", "stock_count", "image_path", "description"]

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"[Preprocess] ✓ Wrote {len(output_rows)} rows → {OUTPUT_CSV}")

    # ── Quick sanity stats ────────────────────────────────────────────────────
    from collections import Counter
    cats = Counter(r["category"] for r in output_rows)
    print("\n[Preprocess] Category distribution:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        pct = count / len(output_rows) * 100
        print(f"  {cat:<15} {count:>5}  ({pct:.1f}%)")

    in_stock_count = sum(1 for r in output_rows if str(r["in_stock"]) in ("True", "true", "1"))
    print(f"\n[Preprocess] In-stock: {in_stock_count} / {len(output_rows)} ({in_stock_count/len(output_rows)*100:.1f}%)")


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download & preprocess Kaggle fashion dataset for Vectra"
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max products to include (default: all ~44K). Use 5000 for Phase 2."
    )
    parser.add_argument(
        "--skip-download", action="store_true",
        help="Skip Kaggle download if data is already present in data/kaggle/raw/"
    )
    args = parser.parse_args()

    if not args.skip_download:
        download_dataset()
    else:
        print("[Download] Skipping download — using existing raw data.")

    styles_csv  = find_styles_csv()
    images_src  = find_images_source()

    preprocess(styles_csv, images_src, limit=args.limit)

    print("\n[Done] Next step:")
    print(f"  python scripts/ingest.py --csv {OUTPUT_CSV} --batch-size 32 --clear")
