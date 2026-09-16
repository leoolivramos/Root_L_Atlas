"""
api/database.py — Pool de conexões asyncpg com SQLAlchemy async
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from config import settings


# Engine principal (pool gerenciado pelo asyncpg)
_engine: AsyncEngine | None = None
# Pool asyncpg nativo (para queries raw de tiles MVT)
_pool: asyncpg.Pool | None = None


async def init_db() -> None:
    """Inicializa engine SQLAlchemy e pool asyncpg."""
    global _engine, _pool

    logger.info("Inicializando pool de conexões PostgreSQL...")

    _engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_min_size,
        max_overflow=settings.db_pool_max_size - settings.db_pool_min_size,
        pool_pre_ping=True,
        pool_recycle=settings.db_pool_max_inactive_connection_lifetime,
        echo=False,
    )

    # Pool asyncpg nativo — mais eficiente para queries raw (MVT)
    dsn = settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        max_inactive_connection_lifetime=settings.db_pool_max_inactive_connection_lifetime,
        command_timeout=30.0,
    )
    logger.success("Pool PostgreSQL inicializado.")


async def close_db() -> None:
    """Fecha todas as conexões."""
    global _engine, _pool
    if _pool:
        await _pool.close()
        logger.info("Pool asyncpg fechado.")
    if _engine:
        await _engine.dispose()
        logger.info("Engine SQLAlchemy fechado.")


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("DB não inicializado. Chame init_db() primeiro.")
    return _engine


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Pool não inicializado. Chame init_db() primeiro.")
    return _pool


@asynccontextmanager
async def get_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Context manager para uma conexão asyncpg do pool."""
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn
