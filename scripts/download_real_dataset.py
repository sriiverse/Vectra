"""
Vectra: Download the fashion-product-images-small dataset from Hugging Face.

Downloads ~44K real fashion product images with metadata.
After downloading, run:
    python scripts/ingest_real_dataset.py

Usage:
    python scripts/download_real_dataset.py
"""

from datasets import load_dataset

if __name__ == "__main__":
    print("[download] Downloading ashraq/fashion-product-images-small...")
    print("[download] This is ~1.5GB and may take several minutes.\n")

    dataset = load_dataset("ashraq/fashion-product-images-small", split="train")

    print(f"\n[download] Done. {len(dataset)} products cached.")
    print("[download] Next step: python scripts/ingest_real_dataset.py")
