"""
Vectra: Real Product Image Downloader (Pexels API)
===================================================
Downloads real product photos from Pexels for each product in your CSV.

REQUIRED: Get a FREE Pexels API key at https://www.pexels.com/api/
Then set it as PEXELS_API_KEY in your .env file.

Usage:
    # Get an API key first, then:
    python scripts/download_real_images.py

    # If you have an API key:
    PEXELS_API_KEY=your_key python scripts/download_real_images.py

This will replace ALL images in data/synthetic/images/ with real photos.
After running, re-ingest:
    python scripts/ingest.py --csv data/synthetic/products.csv --clear
"""

import os
import csv
import time
import requests
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "synthetic" / "products.csv"
IMAGES_DIR = PROJECT_ROOT / "data" / "synthetic" / "images"

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"

HEADERS = {"User-Agent": "Vectra/1.0"}

def search_pexels(query: str, per_page: int = 1) -> str | None:
    if not PEXELS_API_KEY:
        return None
    headers = {"Authorization": PEXELS_API_KEY}
    params = {"query": query, "per_page": per_page, "orientation": "square"}
    try:
        resp = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("photos"):
                return data["photos"][0]["src"]["medium"]
    except Exception:
        pass
    return None

def build_search_query(name: str, color: str, category: str) -> str:
    name_l = name.lower()
    color_l = color.lower() if color else ""
    parts = [name_l]
    if color_l and color_l not in name_l:
        parts.append(color_l)
    if category.lower() not in name_l:
        parts.append(category.lower())
    return ", ".join(parts[:3])

def download_images():
    if PEXELS_API_KEY:
        print(f"[Download] Using Pexels API (key: {PEXELS_API_KEY[:8]}...)")
    else:
        print("[Download] ⚠ No PEXELS_API_KEY set. Using fallback (picsum.photos).")
        print("  Get a free key at https://www.pexels.com/api/")
        print("  Then: PEXELS_API_KEY=your_key python scripts/download_real_images.py\n")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    with open(CSV_PATH, newline="") as f:
        reader = list(csv.DictReader(f))

    total = len(reader)
    print(f"[Download] Downloading images for {total} products...")

    success = 0
    for idx, row in enumerate(reader):
        p_id = int(row["id"])
        name = row["name"]
        color = row["color"]
        category = row["category"]
        filename = f"product_{p_id:04d}.jpg"
        dest_path = IMAGES_DIR / filename

        query = build_search_query(name, color, category)
        img_url = None

        if PEXELS_API_KEY:
            img_url = search_pexels(query)
            time.sleep(0.1)

        if not img_url:
            img_url = f"https://picsum.photos/seed/{p_id}/400/400"

        try:
            resp = requests.get(img_url, headers=HEADERS, timeout=20, allow_redirects=True)
            if resp.status_code == 200 and 'image' in resp.headers.get('content-type', '') and len(resp.content) > 2000:
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
                success += 1
                if (idx + 1) % 10 == 0:
                    print(f"  [{idx+1}/{total}] Downloaded {filename}")
            else:
                print(f"  ✗ Bad response for {filename}: status={resp.status_code} type={resp.headers.get('content-type')} size={len(resp.content)}")
        except Exception as e:
            print(f"  ✗ Failed {filename}: {e}")

        time.sleep(0.2)

    print(f"\n[Download] ✓ {success}/{total} images downloaded to {IMAGES_DIR}")
    if success > 0:
        print("\n  Next step: python scripts/ingest.py --csv data/synthetic/products.csv --clear")

if __name__ == "__main__":
    download_images()
