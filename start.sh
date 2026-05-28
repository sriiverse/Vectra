#!/bin/bash
set -e

# ─── Database Migration ───────────────────────────────────────────
# Run schema.sql against the target database if DATABASE_URL is set.
# This is idempotent (all statements use IF NOT EXISTS).
if [ -n "$DATABASE_URL" ]; then
    echo "[start.sh] Running schema migration..."
    psql "$DATABASE_URL" -f schema.sql 2>&1 | tail -3
    echo "[start.sh] Migration complete."
fi

# ─── Start Uvicorn ────────────────────────────────────────────────
# Railway provides PORT; default to 8000 for local Docker compat.
PORT="${PORT:-8000}"
echo "[start.sh] Starting server on 0.0.0.0:${PORT}..."

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 1 \
    --loop uvloop \
    --http httptools
