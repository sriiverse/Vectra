"""
Vectra: Real Product Image Downloader
=====================================
Downloads 66 real product images from LoremFlickr based on product metadata,
replacing the gray placeholder images in data/synthetic/images/ so the UI
and the CLIP model ingest real product photos.
"""

import os
import csv
import time
import requests
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "synthetic" / "products.csv"
IMAGES_DIR = PROJECT_ROOT / "data" / "synthetic" / "images"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def clean_keywords(name, color, category):
    name_l = name.lower()
    color_l = color.lower() if color else ""
    
    # Specific high-quality keywords for LoremFlickr
    if "t-shirt" in name_l:
        kw = "tshirt,clothing"
    elif "shirt" in name_l:
        kw = "shirt,fashion"
    elif "chinos" in name_l or "pants" in name_l:
        kw = "trousers,clothing"
    elif "leggings" in name_l:
        kw = "leggings,fitness"
    elif "dress" in name_l:
        kw = "dress,fashion"
    elif "jacket" in name_l:
        kw = "jacket,coat"
    elif "blazer" in name_l:
        kw = "blazer,suit"
    elif "polo" in name_l:
        kw = "polo,shirt"
    elif "shorts" in name_l:
        kw = "shorts,clothing"
    elif "sneakers" in name_l:
        kw = "sneakers,shoes"
    elif "shoes" in name_l or "loafers" in name_l:
        kw = "shoes,leather"
    elif "sandals" in name_l or "flops" in name_l:
        kw = "sandals"
    elif "boots" in name_l:
        kw = "boots"
    elif "earbuds" in name_l or "headphones" in name_l:
        kw = "earphones,electronics"
    elif "smartwatch" in name_l:
        kw = "smartwatch"
    elif "speaker" in name_l:
        kw = "speaker,audio"
    elif "keyboard" in name_l:
        kw = "keyboard,computer"
    elif "mouse" in name_l:
        kw = "mouse,computer"
    elif "bulb" in name_l:
        kw = "lightbulb"
    elif "tv" in name_l:
        kw = "television"
    elif "camera" in name_l:
        kw = "camera"
    elif "reader" in name_l:
        kw = "ereader,tablet"
    elif "mug" in name_l:
        kw = "mug,coffee"
    elif "candle" in name_l:
        kw = "candle"
    elif "blanket" in name_l:
        kw = "blanket"
    elif "towel" in name_l:
        kw = "towel"
    elif "tray" in name_l:
        kw = "tray,wood"
    elif "bottle" in name_l:
        kw = "waterbottle"
    elif "plant" in name_l or "pot" in name_l:
        kw = "plant,pot"
    elif "organiser" in name_l:
        kw = "desk organizer"
    elif "frame" in name_l:
        kw = "pictureframe"
    elif "purifier" in name_l:
        kw = "airpurifier"
    elif "vacuum" in name_l:
        kw = "vacuum"
    elif "serum" in name_l or "sunscreen" in name_l or "wash" in name_l or "oil" in name_l:
        kw = "cosmetic,skincare"
    elif "lipstick" in name_l:
        kw = "lipstick,makeup"
    elif "palette" in name_l:
        kw = "eyeshadow,makeup"
    elif "perfume" in name_l:
        kw = "perfume,bottle"
    else:
        kw = f"{category.lower()},product"
        
    if color_l:
        return f"{kw},{color_l}"
    return kw

def download_images():
    print(f"[Download] Reading product metadata from {CSV_PATH}...")
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(CSV_PATH, newline="") as f:
        reader = list(csv.DictReader(f))
        
    total = len(reader)
    print(f"[Download] Starting download of {total} images from LoremFlickr...")
    
    success_count = 0
    for idx, row in enumerate(reader):
        p_id = int(row["id"])
        name = row["name"]
        color = row["color"]
        category = row["category"]
        
        # Determine target file path
        filename = f"product_{p_id:04d}.jpg"
        dest_path = IMAGES_DIR / filename
        
        # Get query keywords
        kw = clean_keywords(name, color, category)
        # We add fashion/product to keywords to make them cleaner
        url = f"https://loremflickr.com/400/400/{kw}"
        
        print(f"[{idx+1}/{total}] Downloading {filename} for '{name}' ({color}) using tags: '{kw}'...")
        
        retry = 3
        while retry > 0:
            try:
                res = requests.get(url, headers=HEADERS, timeout=15)
                if res.status_code == 200 and 'image' in res.headers.get('content-type', ''):
                    with open(dest_path, "wb") as img_file:
                        img_file.write(res.content)
                    success_count += 1
                    break
                else:
                    print(f"  ⚠ Failed status/content type: {res.status_code}, {res.headers.get('content-type')}. Retrying...")
            except Exception as e:
                print(f"  ⚠ Connection error: {e}. Retrying...")
            retry -= 1
            time.sleep(1)
            
        if retry == 0:
            print(f"  ✗ Failed to download {filename} after 3 attempts.")
            
    print(f"\n[Download] Finished. Successfully downloaded {success_count}/{total} images.")

if __name__ == "__main__":
    download_images()
