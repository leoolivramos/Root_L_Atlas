"""
api/main.py — Aplicação FastAPI Principal do RootL Atlas
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from loguru import logger

from config import settings
from database import close_db, init_db
from routers.tiles import router as tiles_router
from routers.features import router as features_router
from routers.search import search_router
from routers.accessibility import router as accessibility_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida da aplicação."""
    logger.info("🗺️  RootL Atlas API iniciando...")
    await init_db()
    logger.success("API pronta para receber requisições.")
    yield
    logger.info("API encerrando...")
    await close_db()


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "tiles", "description": "Mosaicos Vetoriais (MVT) para MapLibre GL"},
        {"name": "features", "description": "Feições GeoJSON individuais"},
        {"name": "search", "description": "Busca alfanumérica"},
        {"name": "acessibilidade", "description": "Análise de acessibilidade a infraestruturas"},
        {"name": "saúde", "description": "Verificação da API"},
    ],
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# Routers
app.include_router(tiles_router)
app.include_router(features_router)
app.include_router(search_router)
app.include_router(accessibility_router)


@app.get("/health", tags=["saúde"], summary="Health Check")
async def health_check() -> dict:
    """Verifica se a API e o banco de dados estão operacionais."""
    from database import get_connection
    try:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT COUNT(*) AS setores FROM atlas.setores_censitarios"
            )
        return {
            "status": "healthy",
            "database": "connected",
            "setores_carregados": row["setores"] if row else 0,
        }
    except Exception as e:
        return {
            "status": "degraded",
            "database": "error",
            "detail": str(e),
        }


@app.get("/", tags=["saúde"], summary="Root")
async def root() -> dict:
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "territory": "Mato Grosso (MT) — Brasil",
        "docs": "/docs",
        "health": "/health",
        "layers": {
            "municipios": "/tiles/municipios/{z}/{x}/{y}",
            "setores": "/tiles/setores/{z}/{x}/{y}",
            "escolas": "/tiles/escolas/{z}/{x}/{y}",
            "saude": "/tiles/saude/{z}/{x}/{y}",
        },
    }
