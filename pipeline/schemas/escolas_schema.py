"""
pipeline/schemas/escolas_schema.py
=====================================
Schema Pandera para validação de escolas na camada Gold.
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
import pandera as pa
from loguru import logger
from pandera import Column, DataFrameSchema

_MT_LAT_MIN, _MT_LAT_MAX = -20.5, -6.5
_MT_LON_MIN, _MT_LON_MAX = -62.0, -49.5

_VALID_DEPENDENCIA = {1, 2, 3, 4}      # Federal, Estadual, Municipal, Privada
_VALID_SITUACAO = {1, 2, 3, 4, 5}      # Em atividade, Paralisada, Extinta, etc.

ESCOLAS_GOLD_SCHEMA = DataFrameSchema(
    columns={
        "co_entidade": Column(
            int,
            nullable=False,
            unique=True,
            checks=pa.Check(lambda s: s > 0, error="co_entidade deve ser positivo"),
        ),
        "no_entidade": Column(str, nullable=False),
        "tp_dependencia": Column(
            int,
            nullable=False,
            checks=pa.Check.isin(_VALID_DEPENDENCIA),
        ),
        "tp_situacao_funcionamento": Column(
            int,
            nullable=True,
            checks=pa.Check.isin(_VALID_SITUACAO),
        ),
        "co_municipio": Column(
            str,
            nullable=False,
            checks=pa.Check(lambda s: s.str.len().isin([6, 7])),
        ),
        "no_municipio": Column(str, nullable=False),
        "ano_censo": Column(
            int,
            nullable=False,
            checks=pa.Check.in_range(2015, 2030),
        ),
    },
    strict=False,
    coerce=True,
)


def validate_escolas_silver(
    gdf: gpd.GeoDataFrame,
    raise_on_failure: bool = True,
) -> gpd.GeoDataFrame:
    """
    Valida GeoDataFrame de escolas contra o schema Gold.

    Validação adicional crítica:
    - Coordenadas NUNCA podem ser no oceano ou fora do Brasil
    - Uma escola no oceano é sinal de erro grave de geocodificação
    """
    df_val = pd.DataFrame(
        {c: gdf[c] for c in ESCOLAS_GOLD_SCHEMA.columns if c in gdf.columns}
    )

    try:
        ESCOLAS_GOLD_SCHEMA.validate(df_val, lazy=True)
    except pa.errors.SchemaErrors as exc:
        err = exc.failure_cases
        logger.error(f"[Pandera/Escolas] {len(err)} violações:\n{err.head(10).to_string()}")
        if raise_on_failure:
            raise RuntimeError(
                f"Pipeline BLOQUEADO: violações de schema em escolas.\n"
                f"{err.head(20).to_string()}"
            ) from exc
        invalid_idx = err["index"].dropna().unique()
        gdf = gdf[~gdf.index.isin(invalid_idx)].copy()

    # Validação geográfica: escola no oceano?
    if hasattr(gdf, "geometry") and gdf.geometry is not None:
        lats = gdf.geometry.y
        lons = gdf.geometry.x
        mask = (
            (lats >= -34.0) & (lats <= 6.0) &
            (lons >= -74.0) & (lons <= -28.0)
        )
        oceano = gdf[~mask]
        if len(oceano) > 0:
            logger.error(
                f"VIOLAÇÃO CRÍTICA: {len(oceano)} escolas com coordenadas "
                f"fora do Brasil (possível: oceano ou outro país)!\n"
                f"  co_entidade: {oceano['co_entidade'].head(5).tolist()}\n"
                f"  lat: {lats[~mask].head(3).tolist()}, lon: {lons[~mask].head(3).tolist()}"
            )
            if raise_on_failure:
                raise RuntimeError(
                    f"Pipeline BLOQUEADO: {len(oceano)} escolas com coordenadas inválidas "
                    "(fora do território brasileiro). Verifique o geocodificador de origem."
                )
            gdf = gdf[mask].copy()

    logger.success(f"  [Pandera/Escolas] {len(gdf):,} escolas válidas")
    return gdf
