"""
pipeline/schemas/setores_schema.py
=====================================
Schema Pandera para validação dos setores censitários na camada Gold.

A validação por schema é o mecanismo que BLOQUEIA o pipeline quando
dados inválidos tentam progredir para a camada de consumo.
Cada violação gera um relatório detalhado com as linhas ofensivas.
"""

from __future__ import annotations

from typing import Any

import geopandas as gpd
import pandas as pd
import pandera as pa
from loguru import logger
from pandera import Column, DataFrameSchema
from pandera.typing import Series


# ─────────────────────────────────────────────────────────────────────────────
# Schema de validação
# ─────────────────────────────────────────────────────────────────────────────

# Bounding box aproximada do Mato Grosso (WGS84)
_MT_LAT_MIN = -20.5
_MT_LAT_MAX = -6.5
_MT_LON_MIN = -62.0
_MT_LON_MAX = -49.5

# Domínio válido de tipos de setor (IBGE)
_VALID_TIPO_SETOR = {1, 2, 3, 4, 5, 6, 7, 8, 9}

# Código UF esperado para MT
_MT_UF_CODE = "51"

SETORES_SILVER_SCHEMA = DataFrameSchema(
    columns={
        "cd_setor": Column(
            str,
            nullable=False,
            unique=True,
            checks=[
                pa.Check(lambda s: s.str.len() == 15, error="cd_setor deve ter 15 dígitos"),
                pa.Check(
                    lambda s: s.str.startswith(_MT_UF_CODE),
                    error=f"cd_setor deve iniciar com {_MT_UF_CODE} (MT)",
                ),
            ],
        ),
        "cd_municipio": Column(
            str,
            nullable=False,
            checks=[
                pa.Check(
                    lambda s: s.str.len().isin([6, 7]),
                    error="cd_municipio deve ter 6 ou 7 dígitos",
                ),
            ],
        ),
        "nm_municipio": Column(str, nullable=False),
        "sg_uf": Column(
            str,
            nullable=False,
            checks=pa.Check.isin(["MT"]),
        ),
        "tipo_setor": Column(
            int,
            nullable=True,
            checks=pa.Check.isin(_VALID_TIPO_SETOR),
        ),
        "area_km2": Column(
            float,
            nullable=True,
            checks=[
                pa.Check(lambda s: s.dropna() > 0, error="area_km2 deve ser positiva"),
                pa.Check(
                    lambda s: s.dropna() < 50_000,
                    error="area_km2 > 50000 km² suspeito para setor censitário",
                ),
            ],
        ),
    },
    checks=[
        # Validação cruzada: geometria deve existir
        pa.Check(
            lambda df: df.index.notna().all(),
            error="DataFrame não pode ter índice nulo",
        ),
    ],
    strict=False,  # Permite colunas extras (geometria, centróide, etc.)
    coerce=True,
)


def validate_setores_silver(
    gdf: gpd.GeoDataFrame,
    raise_on_failure: bool = True,
) -> gpd.GeoDataFrame:
    """
    Valida o GeoDataFrame de setores contra o schema definido.

    Em caso de falha:
    - Loga as linhas ofensivas com detalhes
    - Se raise_on_failure=True, levanta exceção (bloqueia o pipeline)
    - Se raise_on_failure=False, retorna apenas as linhas válidas

    Args:
        gdf: GeoDataFrame de setores (após transformações Silver→Gold)
        raise_on_failure: Se True, bloqueia o pipeline em caso de erros

    Returns:
        GeoDataFrame validado
    """
    # Converte para DataFrame regular para o Pandera (ignora coluna geom)
    df_for_validation = pd.DataFrame(
        {c: gdf[c] for c in SETORES_SILVER_SCHEMA.columns if c in gdf.columns}
    )

    try:
        SETORES_SILVER_SCHEMA.validate(df_for_validation, lazy=True)
        logger.success(f"  [Pandera] Setores válidos: {len(gdf):,} registros")
        return gdf

    except pa.errors.SchemaErrors as exc:
        error_report = exc.failure_cases
        logger.error(
            f"  [Pandera] VIOLAÇÕES detectadas em {len(error_report)} casos!\n"
            f"  Exemplos:\n{error_report.head(10).to_string()}"
        )

        if raise_on_failure:
            raise RuntimeError(
                f"Pipeline BLOQUEADO: {len(error_report)} violações de schema "
                f"nos setores censitários. Revise os dados de entrada.\n"
                f"Erros:\n{error_report.head(20).to_string()}"
            ) from exc

        # Retorna apenas as linhas sem violações
        invalid_indices = error_report["index"].dropna().unique()
        valid_gdf = gdf[~gdf.index.isin(invalid_indices)].copy()
        logger.warning(
            f"  Modo não-estrito: {len(invalid_indices)} linhas removidas. "
            f"Restam {len(valid_gdf):,} setores válidos."
        )
        return valid_gdf


def validate_geometry_within_mt(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Validação adicional: centróides dentro do Mato Grosso.

    Bloqueio obrigatório: uma escola posicionada no oceano ou
    em outro continente deve ser rejeitada com relatório claro.
    """
    if "centroide" not in gdf.columns:
        from transforms.geo_utils import add_centroid_column
        gdf = add_centroid_column(gdf)

    centroids = gdf["centroide"]
    lats = centroids.y
    lons = centroids.x

    mask = (
        (lats >= _MT_LAT_MIN) & (lats <= _MT_LAT_MAX) &
        (lons >= _MT_LON_MIN) & (lons <= _MT_LON_MAX)
    )

    out_of_bounds = gdf[~mask]
    if len(out_of_bounds) > 0:
        logger.error(
            f"VIOLAÇÃO CRÍTICA: {len(out_of_bounds)} setores fora da bbox de MT!\n"
            f"  cd_setor: {out_of_bounds['cd_setor'].head(5).tolist()}\n"
            f"  Centróides: {list(zip(lats[~mask].head(5), lons[~mask].head(5)))}"
        )
        raise RuntimeError(
            f"Pipeline BLOQUEADO: {len(out_of_bounds)} setores com centróide "
            "fora dos limites do Mato Grosso. Verifique a projeção e os dados de entrada."
        )

    return gdf[mask].copy()
