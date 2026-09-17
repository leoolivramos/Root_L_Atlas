"""
scratch/run_queimadas_pipeline.py
Executa a ingestão, transformação e carga dos dados de Queimadas do INPE.
"""
import os
import sys
from pathlib import Path

# Ajusta path
sys.path.insert(0, "/app")

from connectors.inpe_connector import INPEQueimadasConnector
from transforms.bronze_to_silver import inpe_queimadas_to_silver
from transforms.silver_to_gold import inpe_queimadas_to_gold
from loaders.postgis_loader import load_geoparquet_to_postgis
from loguru import logger

LAKEHOUSE = Path(os.getenv("LAKEHOUSE_PATH", "/data"))
BRONZE = LAKEHOUSE / "bronze"
SILVER = LAKEHOUSE / "silver"
GOLD = LAKEHOUSE / "gold"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://atlas:123456@postgres:5432/rootl_atlas")

def main():
    logger.info("Iniciando Ingestão INPE Queimadas...")
    connector = INPEQueimadasConnector(
        bronze_base_path=str(BRONZE),
        minio_endpoint=os.getenv("MINIO_ENDPOINT"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD"),
    )

    # Vamos selecionar os meses do pico de queimadas em MT de 2024 e 2025
    target_months = ["202407", "202408", "202409", "202507", "202508"]
    logger.info(f"Processando meses: {target_months}")
    results = connector.ingest(months=target_months)
    csv_paths = [p for p, _ in results]
    logger.info(f"Bronze finalizado: {len(csv_paths)} arquivos obtidos.")

    if not csv_paths:
        logger.error("Nenhum arquivo gerado!")
        return

    # Bronze -> Silver
    logger.info("Transformando Bronze -> Silver...")
    silver_parquet = inpe_queimadas_to_silver(csv_paths, SILVER / "meio_ambiente")
    logger.info(f"Silver gerado: {silver_parquet}")

    # Silver -> Gold
    logger.info("Transformando Silver -> Gold...")
    municipios_parquet = GOLD / "territorio" / "municipios_mt.parquet"
    focos_gold, resumo_gold = inpe_queimadas_to_gold(
        silver_path=silver_parquet,
        gold_path=GOLD / "meio_ambiente",
        municipios_parquet=municipios_parquet if municipios_parquet.exists() else None,
    )
    logger.info(f"Gold focos: {focos_gold}")
    logger.info(f"Gold resumo: {resumo_gold}")

    # Load -> PostGIS
    logger.info("Carregando para o PostGIS...")
    n_focos = load_geoparquet_to_postgis(
        parquet_path=focos_gold,
        table_name="focos_queimadas",
        pk_column="id",
        database_url=DATABASE_URL,
        if_exists="upsert",
        chunksize=25000,
    )
    logger.success(f"Focos carregados no PostGIS: {n_focos:,}")

    n_resumo = load_geoparquet_to_postgis(
        parquet_path=resumo_gold,
        table_name="queimadas_municipais_resumo",
        pk_column="co_municipio",
        database_url=DATABASE_URL,
        if_exists="replace",
    )
    logger.success(f"Resumo municipal carregado no PostGIS: {n_resumo:,}")

if __name__ == "__main__":
    main()
