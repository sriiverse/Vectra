"""
Vectra: Ingest the ashraq/fashion-product-images-small dataset from Hugging Face.

Replaces the 145 synthetic products with ~44K real fashion products.
Each product has a real photograph, category metadata, color, and price.
"""

import io
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.database import get_conn, put_conn

BATCH_SIZE = 64
DB_BATCH_SIZE = 500

IMAGE_OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "real" / "images"
IMAGE_OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Metadata maps ──────────────────────────────────────────────────

CATEGORY_MAP = {
    "Apparel": "Apparel",
    "Footwear": "Footwear",
    "Personal Care": "Beauty",
    "Home": "Home",
    "Accessories": "Accessories",
}

SUBCATEGORY_MAP = {
    "Topwear": "Tops",
    "Bottomwear": "Bottoms",
    "Dress": "Dresses",
    "Shoes": "Shoes",
    "Sandal": "Sandals",
    "Flip Flops": "Flips",
    "Bags": "Bags",
    "Watches": "Watches",
    "Socks": "Socks",
    "Innerwear": "Innerwear",
    "Sporting Goods": "Sports",
    "Wallets": "Wallets",
    "Belts": "Belts",
    "Jewellery": "Jewellery",
    "Eyewear": "Eyewear",
    "Headwear": "Headwear",
    "Ties": "Ties",
    "Scarves": "Scarves",
    "Loungewear and Nightwear": "Loungewear",
    "Saree": "Saree",
    "Accessories": "Accessories",
    "Apparel Set": "Sets",
    "Cufflinks": "Cufflinks",
    "Stoles": "Stoles",
    "Mufflers": "Mufflers",
    "Gloves": "Gloves",
    "Water Bottle": "Drinkware",
    "Umbrellas": "Umbrellas",
    "Shoe Accessories": "Shoe Accessories",
    "Beauty Accessories": "Beauty",
    "Sports Accessories": "Sports",
    "Bath and Body": "Bath",
    "Fragrance": "Fragrance",
    "Lips": "Lips",
    "Nails": "Nails",
    "Makeup": "Makeup",
    "Skin": "Skin",
    "Skin Care": "Skin",
    "Eyes": "Eyes",
    "Hair": "Hair",
    "Perfumes": "Perfumes",
    "Home Furnishing": "Home",
    "Wristbands": "Wristbands",
    "Mufflers": "Mufflers",
}

COLOR_MAP = {
    "Navy Blue": "Navy", "Navy": "Navy",
    "Steel": "Grey", "Grey": "Grey",
    "Charcoal": "Charcoal", "Black": "Black", "White": "White",
    "Blue": "Blue", "Brown": "Brown",
    "Burgundy": "Burgundy", "Maroon": "Burgundy",
    "Red": "Red", "Green": "Green", "Pink": "Pink",
    "Yellow": "Yellow", "Purple": "Purple", "Orange": "Orange",
    "Gold": "Gold", "Silver": "Silver",
    "Beige": "Beige", "Olive": "Olive", "Khaki": "Khaki",
    "Cream": "Cream", "Multi": "Multicolor",
    "Copper": "Copper", "Bronze": "Bronze",
    "Peach": "Peach", "Mauve": "Purple",
    "Lavender": "Lavender", "Lime": "Green",
    "Teal": "Teal", "Mint": "Mint",
    "Coral": "Coral", "Mushroom": "Beige",
    "Rose": "Rose", "Rust": "Orange",
    "Blush": "Blush", "Melange": "Multicolor",
    "Taupe": "Beige", "Off White": "White",
    "Mustard": "Mustard", "Nude": "Nude",
    "Tan": "Tan", "Coffee Brown": "Brown",
    "Fluorescent Green": "Green", "Sea Green": "Green",
    "Magenta": "Purple", "Turquoise Blue": "Blue",
    "Metallic": "Silver", "Leopard": "Multicolor",
    "Camel": "Tan",
}

PRICE_MAP = {
    "Tshirts": (499, 1999), "Shirts": (699, 2999),
    "Casual Shoes": (999, 4999), "Sports Shoes": (1999, 7999),
    "Formal Shoes": (1499, 5999), "Sandals": (499, 2499),
    "Flip Flops": (299, 1499), "Heels": (999, 5999),
    "Watches": (1999, 9999), "Handbags": (999, 5999),
    "Backpacks": (999, 3999), "Wallets": (499, 2499),
    "Belts": (299, 1499), "Sunglasses": (499, 2999),
    "Perfume and Body Mist": (399, 2499), "Kurtas": (699, 2999),
    "Tops": (399, 1999), "Dresses": (999, 3999),
    "Jeans": (999, 3999), "Shorts": (499, 1999),
    "Track Pants": (599, 1999), "Trousers": (699, 2999),
    "Sweaters": (999, 3999), "Jackets": (1499, 5999),
    "Socks": (199, 799), "Briefs": (199, 999),
    "Boxers": (199, 999), "Bra": (399, 1499),
    "Lipstick": (199, 999), "Nail Polish": (99, 499),
    "Foundation": (399, 1499), "Mascara": (299, 999),
    "Eye Liner": (199, 799), "Skin Care": (299, 1999),
    "Hair": (199, 999), "Shampoo": (199, 999),
    "Soap": (99, 499), "Lotion": (199, 999),
    "Face Wash": (149, 599), "Sunscreen": (299, 999),
}

FOOTWEAR_SIZE = {"Casual Shoes": (5, 13), "Sports Shoes": (5, 13), "Formal Shoes": (6, 12),
                 "Sandals": (5, 11), "Flip Flops": (5, 11), "Heels": (5, 11), "Socks": (5, 13)}

APPAREL_SIZES = ["S", "M", "L", "XL", "XXL"]
APPAREL_SIZE_NUMS = {"S": (1, 2), "M": (2, 3), "L": (3, 4), "XL": (4, 5), "XXL": (5, 6)}


def find_parquet_files():
    """Find the downloaded parquet files in HF cache."""
    cache_root = Path.home() / ".cache" / "huggingface" / "hub"
    pattern = "datasets--ashraq--fashion-product-images-small"
    for d in cache_root.glob(f"{pattern}*/snapshots/*/data/train-*.parquet"):
        return sorted(d.parent.glob("train-*.parquet")) if d.parent else []
    return []


def map_color(ds_color: str) -> str | None:
    if not ds_color or pd.isna(ds_color):
        return None
    return COLOR_MAP.get(ds_color.strip(), ds_color.strip())


def map_category(ds_cat: str) -> str | None:
    if not ds_cat or pd.isna(ds_cat):
        return None
    return CATEGORY_MAP.get(ds_cat.strip())


def map_subcategory(ds_sub: str) -> str | None:
    if not ds_sub or pd.isna(ds_sub):
        return None
    return SUBCATEGORY_MAP.get(ds_sub.strip())


def generate_price(article_type: str) -> float:
    low, high = PRICE_MAP.get(article_type, (499, 2999))
    h = hash(article_type or "generic") & 0xFFFF
    return float(low + (h % max(1, (high - low) // 100)) * 100)


def assign_sizes(article_type: str, master_category: str, sub_category: str):
    article = article_type or ""
    cat = master_category or ""
    sub = sub_category or ""

    if cat == "Footwear":
        lo, hi = FOOTWEAR_SIZE.get(article, (5.0, 13.0))
        return float(lo), float(hi)

    if cat == "Apparel" and sub in ("Topwear", "Bottomwear", "Innerwear", "Loungewear and Nightwear"):
        idx = hash(article + sub) % len(APPAREL_SIZES)
        lo, hi = APPAREL_SIZE_NUMS[APPAREL_SIZES[idx]]
        return float(lo), float(hi)

    return None, None


def decode_image(img_dict) -> Image.Image | None:
    try:
        if isinstance(img_dict, dict):
            b = img_dict.get("bytes")
            if b and isinstance(b, bytes) and len(b) > 100:
                return Image.open(io.BytesIO(b)).convert("RGB")
            p = img_dict.get("path")
            if p:
                return Image.open(p).convert("RGB")
    except Exception:
        return None
    return None


_global_img_counter = 0


def save_image(image: Image.Image) -> str:
    global _global_img_counter
    _global_img_counter += 1
    filename = f"real_{_global_img_counter:06d}.jpg"
    image.save(str(IMAGE_OUT_DIR / filename), "JPEG", quality=85)
    return f"data/real/images/{filename}"


def main():
    from app.embedder import _get_model

    print("[ingest] Loading CLIP model...")
    model = _get_model()
    print("[ingest] CLIP model loaded.")

    parquet_files = find_parquet_files()
    if not parquet_files:
        print("[ingest] ERROR: No parquet files found. Run download script first.")
        return
    print(f"[ingest] Found {len(parquet_files)} parquet file(s): {[p.name for p in parquet_files]}")

    conn = get_conn()

    # Ensure categories include Accessories
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS products_category_check;")
        cur.execute("""
            ALTER TABLE products ADD CONSTRAINT products_category_check
            CHECK (category IN ('Apparel', 'Electronics', 'Home', 'Footwear', 'Beauty', 'Accessories'));
        """)
        conn.commit()
    print("[ingest] Updated category constraint.")

    # Truncate existing products
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE products RESTART IDENTITY CASCADE;")
        conn.commit()
    print("[ingest] Truncated existing products.")

    total_inserted = 0

    for pf in parquet_files:
        print(f"\n[ingest] Reading {pf.name}...")
        df = pd.read_parquet(pf)
        print(f"[ingest]   {len(df)} rows")

        batch_rows = []
        batch_images = []

        for idx, row in df.iterrows():
            image = decode_image(row["image"])
            if image is None:
                continue

            category = map_category(row.get("masterCategory"))
            if category is None:
                continue

            article_type = row.get("articleType", "")
            if pd.isna(article_type):
                article_type = ""

            subcat = map_subcategory(row.get("subCategory"))
            color = map_color(row.get("baseColour"))
            name = row.get("productDisplayName", "")
            if pd.isna(name) or not name:
                name = f"{color or ''} {article_type}".strip() or "Product"

            price = generate_price(article_type)
            size_min, size_max = assign_sizes(article_type, row.get("masterCategory"), row.get("subCategory"))
            img_path = save_image(image)

            batch_rows.append({
                "name": str(name)[:255],
                "category": category,
                "subcategory": subcat,
                "color": color,
                "price": price,
                "in_stock": True,
                "stock_count": 50,
                "image_path": img_path,
                "description": str(name)[:500],
                "size_min": size_min,
                "size_max": size_max,
            })
            batch_images.append(image)

            if len(batch_rows) >= BATCH_SIZE:
                _process_batch(conn, model, batch_rows, batch_images)
                total_inserted += len(batch_rows)
                print(f"  ... {total_inserted} products inserted")
                batch_rows, batch_images = [], []

        if batch_rows:
            _process_batch(conn, model, batch_rows, batch_images)
            total_inserted += len(batch_rows)
            print(f"  ... {total_inserted} products inserted")

    print(f"\n[ingest] Done. {total_inserted} products inserted.")

    # Rebuild HNSW index
    print("[ingest] Rebuilding HNSW index...")
    with conn.cursor() as cur:
        cur.execute("DROP INDEX IF EXISTS products_embedding_hnsw_idx;")
        cur.execute("""
            CREATE INDEX products_embedding_hnsw_idx
            ON products USING hnsw (image_embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """)
        conn.commit()

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM products")
        count = cur.fetchone()[0]
        print(f"[ingest] Verification: {count} products in database.")

    put_conn(conn)
    print("[ingest] Complete.")


def _process_batch(conn, model, batch_rows, batch_images):
    embeddings = model.encode(batch_images, batch_size=BATCH_SIZE, show_progress_bar=False, normalize_embeddings=True)

    values = []
    for i, row in enumerate(batch_rows):
        emb_list = embeddings[i].tolist()
        values.append((
            row["name"], row["category"], row["subcategory"], row["color"],
            row["price"], row["in_stock"], row["stock_count"],
            row["image_path"], row["description"],
            row["size_min"], row["size_max"],
            emb_list,
        ))

    sql = """
        INSERT INTO products
            (name, category, subcategory, color, price, in_stock, stock_count,
             image_path, description, size_min, size_max, image_embedding)
        VALUES %s
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, values, page_size=DB_BATCH_SIZE)
        conn.commit()


if __name__ == "__main__":
    t0 = time.perf_counter()
    main()
    elapsed = time.perf_counter() - t0
    print(f"\n[ingest] Total time: {elapsed / 60:.1f} minutes")
