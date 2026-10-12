"""Database connectivity layer supporting both asyncpg (preferred) and psycopg2 (fallback).

Manages organizations and tenant-scoped audit logging for gate events.
"""

import os
from typing import Any

from app.config import DATABASE_URL

# Try asyncpg first (native async + pooled)
try:
    import asyncpg

    _HAS_ASYNCPG = True
except ImportError:
    asyncpg = None  # type: ignore
    _HAS_ASYNCPG = False

# Fallback to psycopg2
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from starlette.concurrency import run_in_threadpool

    _HAS_PSYCOPG2 = True
except ImportError:
    psycopg2 = None  # type: ignore
    _HAS_PSYCOPG2 = False


_asyncpg_pool: Any = None


def _get_sync_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be set to enable audit logging.")
    return psycopg2.connect(DATABASE_URL)


SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS organizations (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(100) UNIQUE NOT NULL,
        access_key VARCHAR(100) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS gate_events (
        id SERIAL PRIMARY KEY,
        org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
        driver_name VARCHAR(255),
        license_number VARCHAR(255),
        compliance_status VARCHAR(50),
        scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Seed default demo depot organization if none exists
    INSERT INTO organizations (id, name, slug, access_key)
    VALUES (1, 'Main Depot', 'main-depot', 'demo-depot-2026')
    ON CONFLICT (id) DO NOTHING;
"""


async def init_db() -> None:
    """Initialize database and ensure the multi-tenant schema exists."""
    global _asyncpg_pool

    if not DATABASE_URL:
        print("⚠️ DATABASE_URL is not set — audit logging will be unavailable.")
        return

    if _HAS_ASYNCPG:
        try:
            _asyncpg_pool = await asyncpg.create_pool(
                DATABASE_URL, min_size=2, max_size=10
            )
            async with _asyncpg_pool.acquire() as conn:
                await conn.execute(SCHEMA_SQL)
                # Ensure org_id column exists if gate_events was created previously
                await conn.execute("""
                    ALTER TABLE gate_events
                    ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE;
                """)
            print(" Connected to PostgreSQL via asyncpg (pooled, multi-tenant ready)")
            return
        except Exception as exc:
            print(f"⚠️ asyncpg pool creation failed: {exc}, attempting psycopg2 fallback")

    if _HAS_PSYCOPG2:
        def _sync_init():
            conn = _get_sync_conn()
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(SCHEMA_SQL)
                        cur.execute("""
                            ALTER TABLE gate_events
                            ADD COLUMN IF NOT EXISTS org_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE;
                        """)
            finally:
                conn.close()

        await run_in_threadpool(_sync_init)
        print(" Connected to PostgreSQL via psycopg2 (threadpool fallback, multi-tenant ready)")
    else:
        raise RuntimeError("Neither asyncpg nor psycopg2 is available.")


async def close_db() -> None:
    global _asyncpg_pool
    if _asyncpg_pool:
        await _asyncpg_pool.close()
        _asyncpg_pool = None


async def execute_query(query: str, *args) -> None:
    """Execute an INSERT/UPDATE/DELETE query across either driver."""
    global _asyncpg_pool
    if _asyncpg_pool:
        async with _asyncpg_pool.acquire() as conn:
            await conn.execute(query, *args)
    elif _HAS_PSYCOPG2:
        sql = query
        for i in range(len(args), 0, -1):
            sql = sql.replace(f"${i}", "%s")

        def _sync_exec():
            conn = _get_sync_conn()
            try:
                with conn:
                    with conn.cursor() as cur:
                        cur.execute(sql, args)
            finally:
                conn.close()

        await run_in_threadpool(_sync_exec)
    else:
        raise RuntimeError("No database driver available.")


async def fetch_rows(query: str, *args) -> list[dict]:
    """Fetch rows from a SELECT query across either driver."""
    global _asyncpg_pool
    if _asyncpg_pool:
        async with _asyncpg_pool.acquire() as conn:
            records = await conn.fetch(query, *args)
            return [dict(r) for r in records]
    elif _HAS_PSYCOPG2:
        sql = query
        for i in range(len(args), 0, -1):
            sql = sql.replace(f"${i}", "%s")

        def _sync_fetch():
            conn = _get_sync_conn()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, args)
                    return [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()

        return await run_in_threadpool(_sync_fetch)
    else:
        raise RuntimeError("No database driver available.")
