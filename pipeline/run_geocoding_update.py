"""
pipeline/run_geocoding_update.py
================================
Executa a atualização de geocodificação de Escolas (INEP + SEDUC-MT) e
Estabelecimentos de Saúde (CNES/DATASUS) utilizando exclusivamente o pacote cep-to-coords por CEP.

Passos executados:
  1. Garante presença dos dados SEDUC-MT 2021 no Lakehouse Bronze.
  2. Executa transformação Bronze → Silver para Escolas (com cruzamento SEDUC + cep-to-coords).
  3. Executa transformação Bronze → Silver para Saúde (com cep-to-coords por CEP).
  4. Transforma Silver → Gold para Escolas e Saúde (com spatial join com setores censitários).
  5. Recalcula a Acessibilidade Educacional com as coordenadas aprimoradas.
  6. Atualiza as tabelas no PostGIS via upsert/replace.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Garante path de importação
PIPELINE_ROOT = Path(__file__).resolve().parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

from loguru import logger

from connectors.seduc_connector import SEDUCEscolasConnector
from loaders.postgis_loader import load_accessibility_to_postgis, load_geoparquet_to_postgis
from transforms.bronze_to_silver import datasus_cnes_to_silver, inep_escolas_to_silver
from transforms.silver_to_gold import cnes_to_gold, compute_accessibility_euclidean, escolas_to_gold


def main() -> None:
    lakehouse_dir = Path(os.getenv("LAKEHOUSE_PATH", "/data"))
    bronze = lakehouse_dir / "bronze"
    silver = lakehouse_dir / "silver"
    gold = lakehouse_dir / "gold"
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://atlas:123456@postgres:5432/rootl_atlas")

    logger.info("=" * 70)
    logger.info("INICIANDO ATUALIZAÇÃO DE GEOCODIFICAÇÃO (CEP-TO-COORDS + SEDUC-MT)")
    logger.info(f"Lakehouse: {lakehouse_dir}")
    logger.info("=" * 70)

    # 1. SEDUC-MT 2021 Bronze
    seduc_connector = SEDUCEscolasConnector(bronze_base_path=str(bronze))
    seduc_xlsx = seduc_connector.download()
    logger.info(f"[1/6] SEDUC-MT 2021 verificado: {seduc_xlsx}")

    # 2. Escolas Bronze → Silver
    escola_raw_csv = silver / "inep" / "raw" / "escolas_mt_2024.csv"
    if not escola_raw_csv.exists():
        candidates = list(bronze.glob("**/escolas_mt_*.csv")) + list(silver.glob("**/escolas_mt_*.csv"))
        if candidates:
            escola_raw_csv = candidates[0]
        else:
            raise FileNotFoundError(f"Arquivo CSV de escolas não encontrado em {escola_raw_csv}")

    logger.info(f"[2/6] Transformando Escolas Bronze → Silver ({escola_raw_csv})...")
    escolas_silver = inep_escolas_to_silver(
        csv_path=escola_raw_csv,
        silver_path=silver / "escolas",
        seduc_xlsx_path=seduc_xlsx,
    )
    logger.success(f"  Escolas Silver gerado: {escolas_silver}")

    # 3. CNES Bronze → Silver
    cnes_candidates = list(bronze.glob("**/cnes_mt_*.parquet"))
    if not cnes_candidates:
        raise FileNotFoundError("Arquivo Parquet de CNES não encontrado em Bronze")
    cnes_raw_parquet = cnes_candidates[0]

    logger.info(f"[3/6] Transformando CNES Bronze → Silver ({cnes_raw_parquet})...")
    cnes_silver = datasus_cnes_to_silver(
        parquet_path=cnes_raw_parquet,
        silver_path=silver / "saude",
    )
    logger.success(f"  CNES Silver gerado: {cnes_silver}")

    # 4. Silver → Gold (Escolas e CNES)
    setores_gold = gold / "territorio" / "setores_censitarios.parquet"
    if not setores_gold.exists():
        # Tenta em silver se gold ainda não gerado
        setores_gold = silver / "setores_censitarios" / "setores_censitarios_mt.parquet"

    logger.info("[4/6] Transformando Silver → Gold (Escolas e CNES)...")
    escolas_gold = escolas_to_gold(
        silver_path=escolas_silver,
        gold_path=gold / "infraestrutura_educacional",
        setores_gold_path=setores_gold if setores_gold.exists() else None,
    )
    logger.success(f"  Escolas Gold: {escolas_gold}")

    cnes_gold = cnes_to_gold(
        silver_path=cnes_silver,
        gold_path=gold / "saude",
        setores_gold_path=setores_gold if setores_gold.exists() else None,
    )
    logger.success(f"  CNES Gold: {cnes_gold}")

    # 5. Recalcular Acessibilidade Educacional
    if setores_gold.exists() and escolas_gold.exists():
        logger.info("[5/6] Recalculando Acessibilidade Educacional...")
        acessib_gold = compute_accessibility_euclidean(
            setores_gold_path=setores_gold,
            escolas_gold_path=escolas_gold,
            gold_path=gold / "acessibilidade",
        )
        logger.success(f"  Acessibilidade Gold: {acessib_gold}")
    else:
        acessib_gold = None
        logger.warning("  Acessibilidade ignorada por ausência de setores censitários Gold.")

    # 6. Carga PostGIS
    logger.info("[6/6] Carregando dados no PostGIS...")
    n_escolas = load_geoparquet_to_postgis(
        parquet_path=escolas_gold,
        table_name="escolas",
        pk_column="co_entidade",
        database_url=database_url,
        if_exists="upsert",
    )
    logger.success(f"  {n_escolas:,} escolas carregadas/atualizadas no PostGIS")

    n_cnes = load_geoparquet_to_postgis(
        parquet_path=cnes_gold,
        table_name="estabelecimentos_saude",
        pk_column="co_cnes",
        database_url=database_url,
        if_exists="replace",
        chunksize=10_000,
    )
    logger.success(f"  {n_cnes:,} estabelecimentos de saúde carregados no PostGIS")

    if acessib_gold and acessib_gold.exists():
        n_acessib = load_accessibility_to_postgis(
            parquet_path=acessib_gold,
            database_url=database_url,
        )
        logger.success(f"  {n_acessib:,} métricas de acessibilidade atualizadas no PostGIS")

    logger.info("=" * 70)
    logger.success("ATUALIZAÇÃO DE GEOCODIFICAÇÃO CONCLUÍDA COM SUCESSO!")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
