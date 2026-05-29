"""
Vectra: Database connection and utilities.
Provides a simple, connection-pooled interface to PostgreSQL via psycopg2.
Supports both DATABASE_URL (production / Railway) and individual DB_* vars (local).
"""

import os
import threading
import psycopg2
import psycopg2.pool
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------
# Connection pool — reuse connections across requests instead of
# opening a new TCP connection on every API call.
# ---------------------------------------------------------------
_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_lock = threading.Lock()


def _build_dsn() -> str:
    """Build a PostgreSQL DSN from DATABASE_URL or individual env vars."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "vectra")
    password = os.getenv("DB_PASSWORD", "vectra_secret")
    dbname = os.getenv("DB_NAME", "vectra_db")
    return f"host={host} port={port} dbname={dbname} user={user} password={password}"


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            _pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=_build_dsn(),
            )
    return _pool


def get_conn():
    conn = get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        conn = psycopg2.connect(_build_dsn())
    return conn


def put_conn(conn):
    get_pool().putconn(conn)


def close_pool():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None
