"""
pipeline/loaders/postgis_loader.py
=====================================
Carregamento de dados Gold para PostgreSQL/PostGIS.

Responsabilidades:
- Lê GeoParquet Gold com GeoPandas
- Realiza upsert por chave primária (insert + update)
- Cria/atualiza índices GiST após carga
- Calcula centróides no PostGIS (mais preciso que Python para polígonos complexos)
- Atualiza métricas de acessibilidade
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import geopandas as gpd
import pandas as pd
import psycopg2
from loguru import logger
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert


def get_engine(database_url: str | None = None):
    """Cria engine SQLAlchemy para o banco PostGIS."""
    url = database_url or os.environ["DATABASE_URL"]
    # Substitui asyncpg por psycopg2 para carga síncrona
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    return create_engine(url, pool_pre_ping=True)


def load_geoparquet_to_postgis(
    parquet_path: Path,
    table_name: str,
    pk_column: str,
    schema: str = "atlas",
    database_url: str | None = None,
    if_exists: Literal["replace", "append", "upsert"] = "upsert",
    chunksize: int = 5_000,
) -> int:
    """
    Carrega um GeoParquet Gold para uma tabela PostGIS.

    Args:
        parquet_path: Path do GeoParquet
        table_name: Nome da tabela de destino
        pk_column: Coluna de chave primária (para upsert)
        schema: Schema PostgreSQL
        database_url: URL de conexão
        if_exists: Estratégia de conflito
        chunksize: Linhas por lote

    Returns:
        Número de registros inseridos/atualizados
    """
    logger.info(f"[PostGIS Loader] Carregando {parquet_path.name} → {schema}.{table_name}")

    try:
        gdf = gpd.read_parquet(parquet_path)
    except Exception:
        gdf = pd.read_parquet(parquet_path)
    logger.info(f"  {len(gdf):,} registros lidos")

    # Remove colunas não existentes na tabela destino (ex: bbox)
    cols_to_drop = [c for c in gdf.columns if c.startswith("bbox")]
    if cols_to_drop:
        gdf = gdf.drop(columns=cols_to_drop)

    # Renomeia coluna de geometria para 'geom' (padrão PostGIS)
    if hasattr(gdf, "rename_geometry") and "geometry" in gdf.columns:
        gdf = gdf.rename_geometry("geom")
    elif "geometry" in gdf.columns:
        gdf = gdf.rename(columns={"geometry": "geom"})

    engine = get_engine(database_url)
    total_loaded = 0

    # Inspeciona colunas da tabela de destino no PostGIS para evitar erros com colunas extras
    with engine.connect() as conn:
        res = conn.execute(text(
            f"SELECT column_name FROM information_schema.columns WHERE table_schema = '{schema}' AND table_name = '{table_name}'"
        ))
        db_cols = {row[0] for row in res}

    if db_cols:
        cols_to_keep = [c for c in gdf.columns if c in db_cols]
        # Se 'id' é gerado pelo banco via sequence (ou contém nulos), remove do dataframe
        if "id" in cols_to_keep and (pk_column != "id" or gdf["id"].isna().any()):
            cols_to_keep.remove("id")
        gdf = gdf[cols_to_keep]

    with engine.connect() as conn:
        if if_exists == "replace":
            conn.execute(text(f"DELETE FROM {schema}.{table_name}"))
            conn.commit()

        # Carga em chunks utilizando psycopg2 execute_values (alta performance, zero geoalchemy2)
        for i in range(0, len(gdf), chunksize):
            chunk = gdf.iloc[i : i + chunksize].copy()
            _upsert_chunk(chunk, table_name, schema, pk_column, engine, if_exists=if_exists)
            total_loaded += len(chunk)
            logger.debug(
                f"  Chunk {i//chunksize + 1}: {total_loaded:,}/{len(gdf):,} registros"
            )

    # Atualiza centróide calculado pelo PostGIS (mais preciso para polígonos complexos)
    _update_centroids_in_postgis(table_name, schema, engine)

    # Atualiza estatísticas do planer
    with engine.connect() as conn:
        conn.execute(text(f"ANALYZE {schema}.{table_name}"))
        conn.commit()

    logger.success(
        f"[PostGIS Loader] {total_loaded:,} registros → {schema}.{table_name}"
    )
    return total_loaded


def _upsert_chunk(
    chunk: gpd.GeoDataFrame | pd.DataFrame,
    table_name: str,
    schema: str,
    pk_column: str,
    engine,
    if_exists: str = "upsert",
) -> None:
    """
    Insere/atualiza registros no PostGIS em alta performance com execute_values.
    Suporta campos espaciais WKT (geom, centroide) convertidos transparentemente.
    """
    from psycopg2.extras import execute_values

    df = pd.DataFrame(chunk)
    if "geom" in df.columns:
        df["geom"] = df["geom"].apply(
            lambda g: g.wkt if g is not None and hasattr(g, "wkt") and not g.is_empty else None
        )
    if "centroide" in df.columns:
        df["centroide"] = df["centroide"].apply(
            lambda g: g.wkt if g is not None and hasattr(g, "wkt") and not g.is_empty else None
        )

    cols = [c for c in df.columns]
    col_list = ", ".join(f'"{c}"' for c in cols)

    geom_cols = {"geom", "centroide"} & set(cols)
    values_template = []
    for col in cols:
        if col in geom_cols:
            values_template.append("ST_GeomFromText(%s, 4326)")
        else:
            values_template.append("%s")
    val_template = "(" + ", ".join(values_template) + ")"

    if if_exists == "upsert" and pk_column in cols:
        non_pk_cols = [c for c in cols if c != pk_column]
        update_set = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in non_pk_cols)
        sql = f"""
            INSERT INTO {schema}.{table_name} ({col_list})
            VALUES %s
            ON CONFLICT ("{pk_column}") DO UPDATE SET {update_set}
        """
    elif if_exists in ("replace", "append"):
        sql = f"""
            INSERT INTO {schema}.{table_name} ({col_list})
            VALUES %s
        """
    else:
        sql = f"""
            INSERT INTO {schema}.{table_name} ({col_list})
            VALUES %s
            ON CONFLICT DO NOTHING
        """

    records = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in df.itertuples(index=False, name=None)
    ]

    raw_conn = engine.raw_connection()
    try:
        with raw_conn.cursor() as cur:
            execute_values(cur, sql, records, template=val_template, page_size=2000)
        raw_conn.commit()
    finally:
        raw_conn.close()


def _update_centroids_in_postgis(
    table_name: str,
    schema: str,
    engine,
) -> None:
    """
    Atualiza a coluna centroide usando ST_PointOnSurface do PostGIS.
    Mais robusto que o centróide geométrico para polígonos côncavos.
    """
    try:
        with engine.connect() as conn:
            res = conn.execute(text(
                f"SELECT 1 FROM information_schema.columns WHERE table_schema = '{schema}' AND table_name = '{table_name}' AND column_name = 'centroide'"
            ))
            if not res.fetchone():
                return

            sql = f"""
                UPDATE {schema}.{table_name}
                SET centroide = ST_PointOnSurface(geom)
                WHERE geom IS NOT NULL
                  AND (centroide IS NULL OR ST_IsEmpty(centroide))
            """
            result = conn.execute(text(sql))
            conn.commit()
            logger.info(
                f"  Centróides atualizados via PostGIS: {result.rowcount} registros"
            )
    except Exception as e:
        logger.warning(f"  Não foi possível atualizar centróides: {e}")


def load_accessibility_to_postgis(
    parquet_path: Path,
    database_url: str | None = None,
    schema: str = "atlas",
) -> int:
    """Carrega tabela de acessibilidade (sem geometria) para PostGIS."""
    logger.info(f"[PostGIS Loader] Carregando acessibilidade...")

    df = pd.read_parquet(parquet_path)
    engine = get_engine(database_url)

    with engine.connect() as conn:
        conn.execute(text(f"DELETE FROM {schema}.acessibilidade_educacional"))
        conn.commit()

    df.to_sql(
        "acessibilidade_educacional",
        con=engine,
        schema=schema,
        if_exists="append",
        index=False,
        chunksize=10_000,
    )

    with engine.connect() as conn:
        conn.execute(text(f"ANALYZE {schema}.acessibilidade_educacional"))
        conn.commit()

    logger.success(f"[PostGIS Loader] Acessibilidade: {len(df):,} registros")
    return len(df)
