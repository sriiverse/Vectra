# Vectra — Deployment Guide

## Option 1: Hugging Face Spaces (Free, 16GB RAM)

1. **Create a Supabase project** (free tier)
   - Go to [supabase.com](https://supabase.com) → New project
   - Once created, go to **SQL Editor** and run:
     ```sql
     CREATE EXTENSION IF NOT EXISTS vector;
     ```
   - Go to **Project Settings → Database** → copy the **Connection string** (URI)

2. **Create a HF Space**
   - Go to [huggingface.co/spaces](https://huggingface.co/spaces) → Create new Space
   - Name: `vectra`, SDK: **Docker**
   - Push this repo to the Space (or link your GitHub)

3. **Set environment variables** in HF Space → Settings → Repository Secrets:
   - `DATABASE_URL` = Supabase connection string
   - `PORT` = `7860`

4. **Build & deploy** — the Space auto-builds. First deploy will take 5-10 minutes
   (downloads ML models + builds Docker image)

5. **Ingest data** — once deployed, run in the Space logs:
   ```bash
   python scripts/generate_synthetic.py && python scripts/ingest.py --csv data/synthetic/products.csv
   ```

6. **Get real images** (two options):
   ```bash
   # Option A: Pexels photos for synthetic products (~3 min)
   python scripts/download_real_images.py && python scripts/ingest.py --csv data/synthetic/products.csv --clear

   # Option B: ~44K real fashion products from HF (~10 min, 1.5GB download)
   python scripts/download_real_dataset.py && python scripts/ingest_real_dataset.py
   ```

7. **Run evaluation** to confirm everything works:
   ```bash
   python scripts/evaluate.py --compare
   ```

Your app will be live at `https://vectra-<username>.hf.space`

## Option 2: Render ($14/month)

1. Create a Render PostgreSQL (with pgvector support)
2. Create a Render Web Service from your GitHub repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add env vars: `DATABASE_URL`, `TEXT_WEIGHT=0.3`, `DEFAULT_TOP_K_RETRIEVAL=50`, `DEFAULT_TOP_N_RERANK=10`
6. After deploy, run ingest scripts as one-off jobs
