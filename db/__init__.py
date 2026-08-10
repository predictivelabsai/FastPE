"""Database connection helpers.

We keep this deliberately thin — plain psycopg connection pool + a SQLAlchemy
engine for places where parameter binding + pandas io is more ergonomic.
Schemas are always qualified (`pehero.*`, `pehero_rag.*`) in SQL; we
never rely on `search_path`.
"""

from __future__ import annotations

import atexit
import os
import threading
from contextlib import contextmanager

import psycopg
from psycopg_pool import ConnectionPool
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from utils.config import settings

_pool: ConnectionPool | None = None
_engine: Engine | None = None
_lock = threading.Lock()

def pool() -> ConnectionPool:
    global _pool
    if _pool is not None:
        return _pool
    with _lock:
        if _pool is None:
            connection_pool = ConnectionPool(
                conninfo=settings().db_url,
                min_size=int(os.getenv("DB_POOL_MIN_SIZE", "0")),
                max_size=int(os.getenv("DB_POOL_MAX_SIZE", "3")),
                timeout=float(os.getenv("DB_POOL_TIMEOUT", "10")),
                max_lifetime=float(os.getenv("DB_POOL_RECYCLE", "1800")),
                max_idle=float(os.getenv("DB_POOL_MAX_IDLE", "300")),
                kwargs={"application_name": os.getenv("DB_APPLICATION_NAME", "fastpe")},
                check=ConnectionPool.check_connection,
                open=False,
            )
            connection_pool.open()
            _pool = connection_pool
    return _pool


@contextmanager
def connect():
    with pool().connection() as conn:
        yield conn


def engine() -> Engine:
    """Return a singleton SQLAlchemy facade without a second retained pool."""
    global _engine
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is None:
            _engine = create_engine(
                settings().db_url,
                poolclass=NullPool,
                connect_args={
                    "application_name": os.getenv("DB_APPLICATION_NAME", "fastpe")
                },
            )
    return _engine


def close_database_pools() -> None:
    """Dispose process database resources at shutdown or during tests."""
    global _pool, _engine
    with _lock:
        connection_pool, sqlalchemy_engine = _pool, _engine
        _pool = None
        _engine = None
    if connection_pool is not None:
        connection_pool.close()
    if sqlalchemy_engine is not None:
        sqlalchemy_engine.dispose()


atexit.register(close_database_pools)


def fetch_all(sql: str, params: tuple | dict | None = None) -> list[dict]:
    with connect() as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def fetch_one(sql: str, params: tuple | dict | None = None) -> dict | None:
    with connect() as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(sql: str, params: tuple | dict | None = None) -> None:
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        conn.commit()
