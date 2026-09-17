"""
api/routers/tiles.py
======================
Endpoint de Mosaicos Vetoriais (MVT) — MapLibre GL.

Arquitetura:
- Geração de tiles 100% no PostgreSQL via ST_AsMVT + ST_TileEnvelope
- Zero serialização no servidor Python (bytes binários diretos)
- Zoom-level guards para prevenir sobrecarga
- Headers de cache HTTP adequados para proxies e CDN

Formato: application/vnd.mapbox-vector-tile
URL: GET /tiles/{layer}/{z}/{x}/{y}
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response
from loguru import logger

from config import settings
from database import get_connection

router = APIRouter(prefix="/tiles", tags=["tiles"])

# Camadas disponíveis e suas funções PostGIS correspondentes
LAYER_FUNCTIONS = {
    "municipios": ("atlas.get_mvt_municipios", settings.mvt_zoom_municipios_min),
    "setores": ("atlas.get_mvt_setores", settings.mvt_zoom_setores_min),
    "escolas": ("atlas.get_mvt_escolas", settings.mvt_zoom_pontos_min),
    "saude": ("atlas.get_mvt_saude", settings.mvt_zoom_pontos_min),
    "malha_viaria": ("atlas.get_mvt_malha_viaria", 5),
    "queimadas": ("atlas.get_mvt_queimadas", 5),
}

CONTENT_TYPE_MVT = "application/vnd.mapbox-vector-tile"


@router.get(
    "/{layer}/{z}/{x}/{y}",
    response_class=Response,
    summary="Mosaico Vetorial (MVT)",
    description=(
        "Gera um tile MVT para a camada e coordenada de tile especificadas. "
        "O tile é gerado diretamente pelo PostGIS via ST_AsMVT, "
        "garantindo máxima eficiência e suporte a índices espaciais GiST."
    ),
    responses={
        200: {"content": {CONTENT_TYPE_MVT: {}}},
        204: {"description": "Tile vazio (sem feições neste tile)"},
        400: {"description": "Camada ou zoom inválido"},
        404: {"description": "Camada não encontrada"},
    },
)
async def get_tile(
    layer: Annotated[str, Path(description="Nome da camada (municipios, setores, escolas, saude)")],
    z: Annotated[int, Path(ge=0, le=22, description="Zoom level")],
    x: Annotated[int, Path(ge=0, description="Tile X")],
    y: Annotated[int, Path(ge=0, description="Tile Y")],
) -> Response:
    """
    Retorna um tile MVT binário para uso com MapLibre GL.

    O PostGIS:
    1. Calcula o envelope geográfico do tile (ST_TileEnvelope)
    2. Filtra geometrias que intersectam o tile (GiST index)
    3. Simplifica geometrias proporcionalmente ao zoom
    4. Serializa para formato MVT binário (ST_AsMVT)

    Retorna 204 se não há feições no tile (MapLibre trata isso corretamente).
    """
    if layer not in LAYER_FUNCTIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Camada '{layer}' não encontrada. "
                   f"Disponíveis: {list(LAYER_FUNCTIONS.keys())}",
        )

    func_name, zoom_min = LAYER_FUNCTIONS[layer]

    if z < zoom_min:
        # Tile vazio — zoom muito baixo para esta camada
        return Response(
            content=b"",
            status_code=204,
            headers=_cache_headers(max_age=3600),
        )

    sql = f"SELECT {func_name}($1, $2, $3)"

    try:
        async with get_connection() as conn:
            row = await conn.fetchrow(sql, z, x, y)
    except Exception as exc:
        logger.error(f"Erro ao gerar tile {layer}/{z}/{x}/{y}: {exc}")
        raise HTTPException(status_code=500, detail="Erro interno ao gerar tile")

    tile_data: bytes | None = row[0] if row else None

    # A função PostGIS pode retornar b'' (bytes vazio) quando não há feições no tile.
    # Tratamos len(tile_data) == 0 como tile vazio → 204 No Content.
    if not tile_data or len(tile_data) == 0:
        return Response(
            content=b"",
            status_code=204,
            headers=_cache_headers(max_age=300),
        )

    # Servir o tile MVT bruto (sem gzip) — MapLibre GL lê bytes MVT diretamente.
    # Content-Encoding: gzip causa falhas silenciosas com alguns clientes/proxies.
    return Response(
        content=tile_data,
        status_code=200,
        media_type=CONTENT_TYPE_MVT,
        headers={
            **_cache_headers(max_age=settings.tile_cache_max_age),
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "*",
        },
    )


def _cache_headers(max_age: int = 3600) -> dict[str, str]:
    """Gera headers HTTP de cache para tiles."""
    return {
        "Cache-Control": f"public, max-age={max_age}, stale-while-revalidate=60",
        "Vary": "Accept-Encoding",
    }


@router.get(
    "/{layer}/metadata",
    summary="Metadados da camada de tiles",
    description="Retorna metadados TileJSON para configuração do MapLibre GL.",
)
async def get_layer_metadata(layer: str) -> dict:
    """TileJSON 3.0 para configuração automática do MapLibre."""
    if layer not in LAYER_FUNCTIONS:
        raise HTTPException(status_code=404, detail=f"Camada '{layer}' não encontrada")

    _, zoom_min = LAYER_FUNCTIONS[layer]

    return {
        "tilejson": "3.0.0",
        "name": f"RootL Atlas — {layer}",
        "description": f"Camada {layer} do RootL Atlas (Mato Grosso)",
        "version": "1.0.0",
        "attribution": "RootL Atlas | IBGE | INEP | OpenStreetMap contributors",
        "scheme": "xyz",
        "tiles": [f"/tiles/{layer}/{{z}}/{{x}}/{{y}}"],
        "minzoom": zoom_min,
        "maxzoom": 18,
        "bounds": [-62.0, -20.0, -49.5, -6.5],  # Mato Grosso
        "center": [-55.9, -12.6, zoom_min + 2],
        "vector_layers": [
            {
                "id": layer,
                "description": f"Camada {layer}",
                "minzoom": zoom_min,
                "maxzoom": 18,
            }
        ],
    }
