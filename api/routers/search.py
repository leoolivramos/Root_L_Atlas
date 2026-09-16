"""
api/routers/search.py — Busca alfanumérica de feições
api/routers/accessibility.py — Métricas de acessibilidade
"""

# ── search.py ────────────────────────────────────────────────────────────────
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import ORJSONResponse
from loguru import logger

from database import get_connection

search_router = APIRouter(prefix="/search", tags=["search"])


@search_router.get(
    "",
    summary="Busca de feições por texto",
    response_class=ORJSONResponse,
)
async def search_features(
    q: str = Query(..., min_length=2, description="Texto de busca"),
    layer: str = Query("all", description="Camada: municipios, escolas, setores, all"),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    """
    Busca textual usando pg_trgm (similaridade fuzzy).
    Retorna lista de feições com id, nome e bounding box.
    """
    results = []

    async with get_connection() as conn:
        if layer in ("municipios", "all"):
            rows = await conn.fetch(
                """
                SELECT
                    'municipio' AS tipo,
                    cd_municipio AS id,
                    nm_municipio AS nome,
                    ST_XMin(geom::box2d) AS xmin,
                    ST_YMin(geom::box2d) AS ymin,
                    ST_XMax(geom::box2d) AS xmax,
                    ST_YMax(geom::box2d) AS ymax,
                    similarity(unaccent(nm_municipio), unaccent($1)) AS score
                FROM atlas.municipios_mt
                WHERE unaccent(nm_municipio) % unaccent($1)
                   OR unaccent(nm_municipio) ILIKE '%' || unaccent($1) || '%'
                ORDER BY score DESC, nm_municipio
                LIMIT $2
                """,
                q, limit,
            )
            results.extend([dict(r) for r in rows])

        if layer in ("escolas", "all"):
            rows = await conn.fetch(
                """
                SELECT
                    'escola' AS tipo,
                    co_entidade::text AS id,
                    no_entidade AS nome,
                    ST_X(geom) - 0.01 AS xmin,
                    ST_Y(geom) - 0.01 AS ymin,
                    ST_X(geom) + 0.01 AS xmax,
                    ST_Y(geom) + 0.01 AS ymax,
                    similarity(unaccent(no_entidade), unaccent($1)) AS score,
                    no_municipio AS municipio,
                    nm_dependencia AS rede
                FROM atlas.escolas
                WHERE unaccent(no_entidade) % unaccent($1)
                   OR unaccent(no_entidade) ILIKE '%' || unaccent($1) || '%'
                ORDER BY score DESC, no_entidade
                LIMIT $2
                """,
                q, limit,
            )
            results.extend([dict(r) for r in rows])

    # Ordena globalmente por score
    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    return {
        "query": q,
        "count": len(results),
        "results": results[:limit],
    }
