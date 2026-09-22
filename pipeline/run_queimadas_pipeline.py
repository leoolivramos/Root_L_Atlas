"""
pipeline/run_queimadas_pipeline.py
====================================
Executa a ingestão histórica e incremental dos dados de Queimadas do INPE.

Estratégia de ingestão:
  1. Anuais (todos satélites) — 2020–2025:
     focos/csv/anual/Brasil_todos_sats/focos_br_todos-sats_YYYY.zip
     → Bronze: focos_queimadas_mt_YYYY.csv (filtrado para MT on-the-fly)

  2. Mensais (todos satélites) — 2026 em diante:
     focos/csv/mensal/Brasil/focos_mensal_br_YYYYMM.{csv|zip}
     → Bronze: focos_queimadas_mt_YYYYMM.csv (filtrado para MT on-the-fly)

O upsert por `id` no PostGIS garante idempotência — re-execuções são seguras.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from connectors.inpe_connector import INPEQueimadasConnector
from transforms.bronze_to_silver import inpe_queimadas_to_silver
from transforms.silver_to_gold import inpe_queimadas_to_gold
from loaders.postgis_loader import load_geoparquet_to_postgis
from loguru import logger

LAKEHOUSE = Path(os.getenv("LAKEHOUSE_PATH", "/data"))
BRONZE = LAKEHOUSE / "bronze" / "meio_ambiente" / "queimadas"
SILVER = LAKEHOUSE / "silver"
GOLD = LAKEHOUSE / "gold"
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://atlas:123456@postgres:5432/rootl_atlas")

# ─── Configuração do range histórico ─────────────────────────────────────────

# Anos completos disponíveis na fonte anual Brasil_todos_sats (todos os satélites)
ANOS_HISTORICOS = list(range(2020, 2026))   # 2020, 2021, 2022, 2023, 2024, 2025

# Meses de 2026 ainda em curso (ingeridos via endpoint mensal)
ANO_MENSAL_FROM = 2026


def main():
    logger.info("=" * 60)
    logger.info("Iniciando ingestão INPE Queimadas (2020 → hoje)")
    logger.info("=" * 60)

    connector = INPEQueimadasConnector(
        bronze_base_path=str(BRONZE),
        minio_endpoint=os.getenv("MINIO_ENDPOINT"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD"),
    )

    csv_paths: list[Path] = []

    # ── FASE 1: Anuais (todos satélites) — 2020–2025 ─────────────────────────
    logger.info(f"[Fase 1] Ingestão anual todos-satélites: {ANOS_HISTORICOS}")
    annual_results = connector.ingest_annual_todos_sats(years=ANOS_HISTORICOS)
    csv_paths.extend(p for p, _ in annual_results)
    logger.info(f"[Fase 1] {len(annual_results)} arquivo(s) anuais obtidos.")

    # ── FASE 2: Mensais — 2026 em diante ─────────────────────────────────────
    current_year = datetime.now(tz=timezone.utc).year
    if ANO_MENSAL_FROM <= current_year:
        logger.info(f"[Fase 2] Ingestão mensal: {ANO_MENSAL_FROM}–{current_year}")
        monthly_results = connector.ingest(year_from=ANO_MENSAL_FROM)
        csv_paths.extend(p for p, _ in monthly_results)
        logger.info(f"[Fase 2] {len(monthly_results)} arquivo(s) mensais obtidos.")

    if not csv_paths:
        logger.error("Nenhum arquivo Bronze gerado. Abortando pipeline.")
        return

    logger.info(f"Total Bronze: {len(csv_paths)} arquivo(s) para transformação.")

    # ── Bronze → Silver ───────────────────────────────────────────────────────
    logger.info("Transformando Bronze → Silver...")
    silver_parquet = inpe_queimadas_to_silver(csv_paths, SILVER / "meio_ambiente")
    logger.info(f"Silver gerado: {silver_parquet}")

    # ── Silver → Gold ─────────────────────────────────────────────────────────
    logger.info("Transformando Silver → Gold...")
    municipios_parquet = GOLD / "territorio" / "municipios_mt.parquet"
    focos_gold, resumo_gold = inpe_queimadas_to_gold(
        silver_path=silver_parquet,
        gold_path=GOLD / "meio_ambiente",
        municipios_parquet=municipios_parquet if municipios_parquet.exists() else None,
    )
    logger.info(f"Gold focos:  {focos_gold}")
    logger.info(f"Gold resumo: {resumo_gold}")

    # ── Gold → PostGIS ────────────────────────────────────────────────────────
    logger.info("Carregando para o PostGIS...")

    n_focos = load_geoparquet_to_postgis(
        parquet_path=focos_gold,
        table_name="focos_queimadas",
        pk_column="id",
        database_url=DATABASE_URL,
        if_exists="upsert",   # idempotente — re-execução segura
        chunksize=25_000,
    )
    logger.success(f"Focos carregados: {n_focos:,} registros → atlas.focos_queimadas")

    n_resumo = load_geoparquet_to_postgis(
        parquet_path=resumo_gold,
        table_name="queimadas_municipais_resumo",
        pk_column="co_municipio",
        database_url=DATABASE_URL,
        if_exists="replace",  # resumo sempre recalculado do zero
    )
    logger.success(f"Resumo municipal carregado: {n_resumo:,} registros → atlas.queimadas_municipais_resumo")

    logger.info("=" * 60)
    logger.success("Pipeline INPE Queimadas concluído com sucesso.")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
