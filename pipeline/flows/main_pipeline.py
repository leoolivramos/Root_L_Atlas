"""
pipeline/flows/main_pipeline.py
==================================
Fluxo principal de orquestração — Prefect 2.

Orquestra o pipeline completo de Mato Grosso (MT):
  1. Território & Setores (IBGE 2022)
  2. Educação (INEP Censo Escolar 2024)
  3. Acessibilidade Educacional (Métricas Euclidianas)
  4. Saúde (DATASUS CNES)
  5. Infraestrutura & Mobilidade (OpenStreetMap / Geofabrik)
  6. Segurança Pública (SINESP / MJSP)
  7. Meio Ambiente & Uso do Solo (MapBiomas Coleção 11)

Linhagem de dados registrada nativamente pelo Prefect e MinIO.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Garante que a raiz do pipeline (/app) esteja no sys.path
PIPELINE_ROOT = Path(__file__).resolve().parent.parent
if str(PIPELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))

import typer
from loguru import logger

try:
    from prefect import flow, task
    from prefect.artifacts import create_markdown_artifact
    from prefect.task_runners import ConcurrentTaskRunner
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    def flow(func=None, **kwargs):
        return func if func else lambda f: f
    def task(func=None, **kwargs):
        return func if func else lambda f: f
    class ConcurrentTaskRunner:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Configuração de paths
# ─────────────────────────────────────────────────────────────────────────────

LAKEHOUSE = Path(os.getenv("LAKEHOUSE_PATH", "./data"))
BRONZE = LAKEHOUSE / "bronze"
SILVER = LAKEHOUSE / "silver"
GOLD   = LAKEHOUSE / "gold"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://atlas:123456@localhost:5432/rootl_atlas",
)


# ─────────────────────────────────────────────────────────────────────────────
# Tasks de Ingestão Bronze
# ─────────────────────────────────────────────────────────────────────────────

@task(name="ingest-ibge-setores", retries=3, retry_delay_seconds=60)
def task_ingest_ibge() -> Path:
    """Download da Malha de Setores Censitários do IBGE."""
    from connectors.ibge_connector import IBGESetoresConnector

    connector = IBGESetoresConnector(
        bronze_base_path=str(BRONZE),
        minio_endpoint=os.getenv("MINIO_ENDPOINT"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD"),
    )
    local_path, manifest = connector.ingest()
    logger.info(f"IBGE Bronze: {local_path} | SHA256: {manifest.file_hash[:12]}...")
    return local_path


@task(name="ingest-inep-escolas", retries=3, retry_delay_seconds=60)
def task_ingest_inep(year: int = 2024) -> Path:
    """Download dos Microdados do Censo Escolar — INEP."""
    from connectors.inep_connector import INEPCensoEscolarConnector

    connector = INEPCensoEscolarConnector(
        year=year,
        bronze_base_path=str(BRONZE),
        minio_endpoint=os.getenv("MINIO_ENDPOINT"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD"),
    )
    local_path, manifest = connector.ingest()
    logger.info(f"INEP Bronze: {local_path} | SHA256: {manifest.file_hash[:12]}...")
    return local_path


@task(name="ingest-datasus-cnes", retries=3, retry_delay_seconds=60)
def task_ingest_cnes() -> Path:
    """Download dos Estabelecimentos de Saúde — DATASUS CNES."""
    from connectors.datasus_connector import DATASUSCNESConnector

    connector = DATASUSCNESConnector(
        bronze_base_path=str(BRONZE),
        minio_endpoint=os.getenv("MINIO_ENDPOINT"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD"),
    )
    local_path, manifest = connector.ingest()
    logger.info(f"DATASUS Bronze: {local_path} | Registros: {manifest.record_count}")
    return local_path


@task(name="ingest-osm-malha", retries=3, retry_delay_seconds=60)
def task_ingest_osm() -> Path:
    """Download do extrato OpenStreetMap (Geofabrik)."""
    from connectors.osm_connector import OSMConnector

    connector = OSMConnector(
        bronze_base_path=str(BRONZE),
        minio_endpoint=os.getenv("MINIO_ENDPOINT"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD"),
    )
    local_path, manifest = connector.ingest()
    logger.info(f"OSM Bronze: {local_path} | SHA256: {manifest.file_hash[:12]}...")
    return local_path


@task(name="ingest-inpe-queimadas", retries=3, retry_delay_seconds=60)
def task_ingest_inpe_queimadas(months: list[str] | None = None) -> list[Path]:
    """Baixa focos mensais do INPE já filtrados para Mato Grosso."""
    from connectors.inpe_connector import INPEQueimadasConnector

    connector = INPEQueimadasConnector(
        bronze_base_path=str(BRONZE),
        minio_endpoint=os.getenv("MINIO_ENDPOINT"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD"),
    )
    results = connector.ingest(months=months)
    paths = [path for path, _ in results]
    if not paths:
        raise RuntimeError("Nenhum arquivo mensal de queimadas do INPE foi ingerido.")
    logger.info(f"INPE Queimadas Bronze: {len(paths)} arquivo(s)")
    return paths


@task(name="ingest-sinesp-seguranca", retries=3, retry_delay_seconds=60)
def task_ingest_sinesp(municipios_parquet: Path | None = None) -> Path:
    """Ingestão de estatísticas municipais de segurança pública — SINESP."""
    from connectors.sinesp_connector import SINESPConnector

    connector = SINESPConnector(
        bronze_base_path=str(BRONZE),
        minio_endpoint=os.getenv("MINIO_ENDPOINT"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD"),
    )
    local_path, manifest = connector.ingest(municipios_parquet=municipios_parquet)
    logger.info(f"SINESP Bronze: {local_path} | Registros: {manifest.record_count}")
    return local_path


@task(name="ingest-mapbiomas-cobertura", retries=3, retry_delay_seconds=60)
def task_ingest_mapbiomas(municipios_parquet: Path | None = None) -> Path:
    """Ingestão de dados de cobertura do solo — MapBiomas Coleção 11."""
    from connectors.mapbiomas_connector import MapBiomasConnector

    connector = MapBiomasConnector(
        bronze_base_path=str(BRONZE),
        minio_endpoint=os.getenv("MINIO_ENDPOINT"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER"),
        minio_secret_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD"),
    )
    local_path, manifest = connector.ingest(municipios_parquet=municipios_parquet)
    logger.info(f"MapBiomas Bronze: {local_path} | Registros: {manifest.record_count}")
    return local_path


# ─────────────────────────────────────────────────────────────────────────────
# Tasks de Transformação Silver
# ─────────────────────────────────────────────────────────────────────────────

@task(name="ibge-bronze-to-silver")
def task_ibge_to_silver(zip_path: Path) -> Path:
    """Extrai e transforma dados IBGE para Silver."""
    from connectors.ibge_connector import IBGESetoresConnector
    from transforms.bronze_to_silver import ibge_setores_to_silver

    connector = IBGESetoresConnector(bronze_base_path=str(BRONZE))
    extracted = connector.extract_to_silver(
        zip_path=zip_path,
        silver_path=SILVER / "ibge" / "raw",
    )
    return ibge_setores_to_silver(
        raw_path=extracted,
        silver_path=SILVER / "setores_censitarios",
        uf_filter="51",
    )


@task(name="inep-bronze-to-silver")
def task_inep_to_silver(zip_path: Path) -> Path:
    """Extrai e transforma dados INEP para Silver."""
    from connectors.inep_connector import INEPCensoEscolarConnector
    from transforms.bronze_to_silver import inep_escolas_to_silver

    connector = INEPCensoEscolarConnector(bronze_base_path=str(BRONZE))
    csv_path = connector.extract_escola_csv(
        zip_path=zip_path,
        silver_path=SILVER / "inep" / "raw",
    )
    return inep_escolas_to_silver(
        csv_path=csv_path,
        silver_path=SILVER / "escolas",
    )


@task(name="cnes-bronze-to-silver")
def task_cnes_to_silver(parquet_path: Path, setores_silver: Path | None = None) -> Path:
    """Transforma dados CNES/DATASUS para Silver."""
    from transforms.bronze_to_silver import datasus_cnes_to_silver
    return datasus_cnes_to_silver(
        parquet_path=parquet_path,
        silver_path=SILVER / "saude",
        setores_path=setores_silver,
    )


@task(name="osm-bronze-to-silver")
def task_osm_to_silver(pbf_path: Path) -> Path:
    """Extrai e filtra a malha viária de MT do OSM."""
    from connectors.osm_connector import OSMConnector
    from transforms.bronze_to_silver import osm_highways_to_silver

    connector = OSMConnector(bronze_base_path=str(BRONZE))
    filtered_pbf = connector.extract_mt_roads(
        pbf_path=pbf_path,
        silver_path=SILVER / "osm",
    )
    geojson_path = SILVER / "osm" / "highways_mt.geojson"
    needs_conversion = not geojson_path.exists()
    if not needs_conversion:
        try:
            with geojson_path.open(encoding="utf-8") as geojson_file:
                needs_conversion = not bool(json.load(geojson_file).get("features"))
        except (OSError, ValueError, AttributeError):
            needs_conversion = True
    if needs_conversion:
        connector.convert_to_geojson(filtered_pbf, geojson_path)

    return osm_highways_to_silver(
        geojson_path=geojson_path,
        silver_path=SILVER / "osm",
    )


@task(name="sinesp-bronze-to-silver")
def task_sinesp_to_silver(csv_path: Path) -> Path:
    """Transforma dados SINESP para Silver."""
    from transforms.bronze_to_silver import sinesp_to_silver
    return sinesp_to_silver(
        csv_path=csv_path,
        silver_path=SILVER / "seguranca",
    )


@task(name="mapbiomas-bronze-to-silver")
def task_mapbiomas_to_silver(parquet_path: Path) -> Path:
    """Transforma dados MapBiomas para Silver."""
    from transforms.bronze_to_silver import mapbiomas_to_silver
    return mapbiomas_to_silver(
        parquet_path=parquet_path,
        silver_path=SILVER / "meio_ambiente",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tasks de Transformação Gold
# ─────────────────────────────────────────────────────────────────────────────

@task(name="setores-silver-to-gold")
def task_setores_to_gold(silver_parquet: Path) -> Path:
    """Transforma setores Silver → Gold (e gera municípios)."""
    from transforms.silver_to_gold import setores_to_gold
    return setores_to_gold(
        silver_path=silver_parquet,
        gold_path=GOLD / "territorio",
    )


@task(name="escolas-silver-to-gold")
def task_escolas_to_gold(silver_parquet: Path, setores_gold: Path) -> Path:
    """Transforma escolas Silver → Gold (com spatial join setor)."""
    from transforms.silver_to_gold import escolas_to_gold
    return escolas_to_gold(
        silver_path=silver_parquet,
        gold_path=GOLD / "infraestrutura_educacional",
        setores_gold_path=setores_gold,
    )


@task(name="calcular-acessibilidade")
def task_acessibilidade(setores_gold: Path, escolas_gold: Path) -> Path:
    """Calcula métricas de acessibilidade educacional."""
    from transforms.silver_to_gold import compute_accessibility_euclidean
    return compute_accessibility_euclidean(
        setores_gold_path=setores_gold,
        escolas_gold_path=escolas_gold,
        gold_path=GOLD / "acessibilidade",
    )


@task(name="cnes-silver-to-gold")
def task_cnes_to_gold(silver_parquet: Path, setores_gold: Path) -> Path:
    """Transforma CNES Silver → Gold."""
    from transforms.silver_to_gold import cnes_to_gold
    return cnes_to_gold(
        silver_path=silver_parquet,
        gold_path=GOLD / "saude",
        setores_gold_path=setores_gold,
    )


@task(name="osm-silver-to-gold")
def task_osm_to_gold(silver_parquet: Path) -> Path:
    """Transforma malha viária Silver → Gold."""
    from transforms.silver_to_gold import osm_to_gold
    return osm_to_gold(
        silver_path=silver_parquet,
        gold_path=GOLD / "infraestrutura",
    )


@task(name="sinesp-silver-to-gold")
def task_sinesp_to_gold(silver_parquet: Path, municipios_gold: Path) -> Path:
    """Transforma SINESP Silver → Gold (com polígono municipal)."""
    from transforms.silver_to_gold import sinesp_to_gold
    return sinesp_to_gold(
        silver_path=silver_parquet,
        gold_path=GOLD / "seguranca",
        municipios_gold_path=municipios_gold,
    )


@task(name="mapbiomas-silver-to-gold")
def task_mapbiomas_to_gold(silver_parquet: Path) -> Path:
    """Transforma MapBiomas Silver → Gold."""
    from transforms.silver_to_gold import mapbiomas_to_gold
    return mapbiomas_to_gold(
        silver_path=silver_parquet,
        gold_path=GOLD / "meio_ambiente",
    )


@task(name="inpe-queimadas-bronze-to-silver")
def task_inpe_queimadas_to_silver(csv_paths: list[Path]) -> Path:
    """Consolida os arquivos mensais de queimadas em Silver."""
    from transforms.bronze_to_silver import inpe_queimadas_to_silver
    return inpe_queimadas_to_silver(csv_paths, SILVER / "meio_ambiente")


@task(name="inpe-queimadas-silver-to-gold")
def task_inpe_queimadas_to_gold(silver_parquet: Path, municipios_gold: Path) -> tuple[Path, Path]:
    """Gera focos pontuais e resumo municipal Gold."""
    from transforms.silver_to_gold import inpe_queimadas_to_gold
    return inpe_queimadas_to_gold(
        silver_path=silver_parquet,
        gold_path=GOLD / "meio_ambiente",
        municipios_parquet=municipios_gold,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tasks de Carga PostGIS
# ─────────────────────────────────────────────────────────────────────────────

@task(name="load-setores-postgis")
def task_load_setores(gold_parquet: Path) -> int:
    """Carrega setores censitários e municípios no PostGIS."""
    from loaders.postgis_loader import load_geoparquet_to_postgis

    municipios_parquet = gold_parquet.parent / "municipios_mt.parquet"
    if municipios_parquet.exists():
        load_geoparquet_to_postgis(
            parquet_path=municipios_parquet,
            table_name="municipios_mt",
            pk_column="cd_municipio",
            database_url=DATABASE_URL,
            if_exists="upsert",
        )

    return load_geoparquet_to_postgis(
        parquet_path=gold_parquet,
        table_name="setores_censitarios",
        pk_column="cd_setor",
        database_url=DATABASE_URL,
        if_exists="upsert",
    )


@task(name="load-escolas-postgis")
def task_load_escolas(gold_parquet: Path) -> int:
    """Carrega escolas no PostGIS."""
    from loaders.postgis_loader import load_geoparquet_to_postgis
    return load_geoparquet_to_postgis(
        parquet_path=gold_parquet,
        table_name="escolas",
        pk_column="co_entidade",
        database_url=DATABASE_URL,
        if_exists="upsert",
    )


@task(name="load-acessibilidade-postgis")
def task_load_acessibilidade(parquet_path: Path) -> int:
    """Carrega métricas de acessibilidade no PostGIS."""
    from loaders.postgis_loader import load_accessibility_to_postgis
    return load_accessibility_to_postgis(
        parquet_path=parquet_path,
        database_url=DATABASE_URL,
    )


@task(name="load-cnes-postgis")
def task_load_cnes(gold_parquet: Path) -> int:
    """Carrega estabelecimentos de saúde no PostGIS."""
    from loaders.postgis_loader import load_geoparquet_to_postgis
    return load_geoparquet_to_postgis(
        parquet_path=gold_parquet,
        table_name="estabelecimentos_saude",
        pk_column="co_cnes",
        database_url=DATABASE_URL,
        if_exists="replace",
        chunksize=10_000,
    )


@task(name="load-osm-postgis")
def task_load_osm(gold_parquet: Path) -> int:
    """Carrega malha viária no PostGIS."""
    from loaders.postgis_loader import load_geoparquet_to_postgis
    return load_geoparquet_to_postgis(
        parquet_path=gold_parquet,
        table_name="malha_viaria_osm",
        pk_column="osm_id",
        database_url=DATABASE_URL,
        if_exists="replace",
        chunksize=10_000,
    )


@task(name="load-sinesp-postgis")
def task_load_sinesp(gold_parquet: Path) -> int:
    """Carrega ocorrências de segurança no PostGIS."""
    from loaders.postgis_loader import load_geoparquet_to_postgis
    return load_geoparquet_to_postgis(
        parquet_path=gold_parquet,
        table_name="ocorrencias_seguranca",
        pk_column="id",
        database_url=DATABASE_URL,
        if_exists="replace",
    )


@task(name="load-mapbiomas-postgis")
def task_load_mapbiomas(gold_parquet: Path) -> int:
    """Carrega cobertura do solo no PostGIS."""
    from loaders.postgis_loader import load_geoparquet_to_postgis
    return load_geoparquet_to_postgis(
        parquet_path=gold_parquet,
        table_name="cobertura_solo_mapbiomas",
        pk_column="id",
        database_url=DATABASE_URL,
        if_exists="replace",
    )


@task(name="load-inpe-queimadas-postgis")
def task_load_inpe_queimadas(focos_parquet: Path, resumo_parquet: Path) -> tuple[int, int]:
    """Carrega focos e resumo municipal de queimadas no PostGIS."""
    from loaders.postgis_loader import load_geoparquet_to_postgis
    focos = load_geoparquet_to_postgis(
        parquet_path=focos_parquet,
        table_name="focos_queimadas",
        pk_column="id",
        database_url=DATABASE_URL,
        if_exists="upsert",
        chunksize=25_000,
    )
    resumo = load_geoparquet_to_postgis(
        parquet_path=resumo_parquet,
        table_name="queimadas_municipais_resumo",
        pk_column="co_municipio",
        database_url=DATABASE_URL,
        if_exists="replace",
    )
    return focos, resumo


# ─────────────────────────────────────────────────────────────────────────────
# Fluxo Principal
# ─────────────────────────────────────────────────────────────────────────────

@flow(
    name="rootl-atlas-pipeline-mt",
    description="Pipeline Completo RootL Atlas: Território, Educação, Saúde, Mobilidade, Segurança e Meio Ambiente",
    task_runner=ConcurrentTaskRunner() if PREFECT_AVAILABLE else None,
)
def main_pipeline(
    ano_censo: int = 2024,
    skip_ingest: bool = False,
    dry_run: bool = False,
) -> dict:
    """Fluxo unificado do RootL Atlas cobrindo todas as 8 entidades."""
    start = datetime.now(timezone.utc)
    logger.info(
        f"{'='*60}\n"
        f"  RootL Atlas Pipeline Completo — Mato Grosso\n"
        f"  Início: {start.isoformat()}\n"
        f"  ano_censo={ano_censo}, skip_ingest={skip_ingest}, dry_run={dry_run}\n"
        f"{'='*60}"
    )

    if dry_run:
        _validate_catalog_and_schemas()
        return {"status": "dry_run_ok"}

    # ── 1. Ingestão Bronze ─────────────────────────────────────
    if not skip_ingest:
        ibge_zip = task_ingest_ibge()
        inep_zip = task_ingest_inep(year=ano_censo)
        cnes_parquet = task_ingest_cnes()
        osm_pbf = task_ingest_osm()
        inpe_queimadas_csvs = task_ingest_inpe_queimadas(
            months=[m.strip() for m in os.getenv("INPE_QUEIMADAS_MESES", "202507,202508,202509").split(",") if m.strip()]
        )
    else:
        ibge_zip = next(BRONZE.glob("**/*setores*.*"), None)
        inep_zip = next(BRONZE.glob("**/microdados_*.zip"), None)
        cnes_parquet = next(BRONZE.glob("**/cnes_mt_*.parquet"), None)
        osm_pbf = next(BRONZE.glob("**/*.osm.pbf"), None)
        inpe_queimadas_csvs = sorted((BRONZE / "inpe_bdqueimadas_mensal").glob("focos_queimadas_mt_*.csv"))
        if not ibge_zip or not inep_zip or not inpe_queimadas_csvs:
            raise FileNotFoundError("skip_ingest=True mas arquivos Bronze essenciais não encontrados.")

    # ── 2. Silver & Gold: Território (Setores & Municípios) ────
    setores_silver = task_ibge_to_silver(ibge_zip)
    setores_gold = task_setores_to_gold(setores_silver)
    municipios_gold = setores_gold.parent / "municipios_mt.parquet"

    # Ingestão Bronze contextual (SINESP e MapBiomas usam municípios consolidados)
    sinesp_csv = task_ingest_sinesp(municipios_parquet=municipios_gold)
    mapbiomas_pq = task_ingest_mapbiomas(municipios_parquet=municipios_gold)

    # ── 3. Silver & Gold: Educação & Acessibilidade ────────────
    escolas_silver = task_inep_to_silver(inep_zip)
    escolas_gold = task_escolas_to_gold(escolas_silver, setores_gold)
    acessib_gold = task_acessibilidade(setores_gold, escolas_gold)

    # ── 4. Silver & Gold: Saúde (CNES) ─────────────────────────
    cnes_silver = task_cnes_to_silver(cnes_parquet, setores_silver=setores_silver)
    cnes_gold = task_cnes_to_gold(cnes_silver, setores_gold=setores_gold)

    # ── 5. Silver & Gold: Infraestrutura Viária (OSM) ──────────
    osm_silver = task_osm_to_silver(osm_pbf)
    osm_gold = task_osm_to_gold(osm_silver)

    # ── 6. Silver & Gold: Segurança (SINESP) ───────────────────
    sinesp_silver = task_sinesp_to_silver(sinesp_csv)
    sinesp_gold = task_sinesp_to_gold(sinesp_silver, municipios_gold=municipios_gold)

    # ── 7. Silver & Gold: Meio Ambiente (MapBiomas) ────────────
    mapbiomas_silver = task_mapbiomas_to_silver(mapbiomas_pq)
    mapbiomas_gold = task_mapbiomas_to_gold(mapbiomas_silver)
    queimadas_silver = task_inpe_queimadas_to_silver(inpe_queimadas_csvs)
    queimadas_gold, queimadas_resumo_gold = task_inpe_queimadas_to_gold(
        queimadas_silver,
        municipios_gold,
    )

    # ── 8. Cargas PostGIS ──────────────────────────────────────
    n_setores = task_load_setores(setores_gold)
    n_escolas = task_load_escolas(escolas_gold)
    n_acessib = task_load_acessibilidade(acessib_gold)
    n_cnes = task_load_cnes(cnes_gold)
    n_osm = task_load_osm(osm_gold)
    n_sinesp = task_load_sinesp(sinesp_gold)
    n_mapbiomas = task_load_mapbiomas(mapbiomas_gold)
    n_queimadas, n_queimadas_resumo = task_load_inpe_queimadas(
        queimadas_gold,
        queimadas_resumo_gold,
    )

    end = datetime.now(timezone.utc)
    duration = (end - start).total_seconds()

    result = {
        "status": "success",
        "duration_s": round(duration, 1),
        "setores_censitarios": n_setores,
        "escolas": n_escolas,
        "acessibilidade_educacional": n_acessib,
        "estabelecimentos_saude": n_cnes,
        "malha_viaria_osm": n_osm,
        "ocorrencias_seguranca": n_sinesp,
        "cobertura_solo_mapbiomas": n_mapbiomas,
        "focos_queimadas": n_queimadas,
        "queimadas_municipais_resumo": n_queimadas_resumo,
    }

    logger.success(
        f"\n{'='*60}\n"
        f"  Pipeline Completo Concluído em {duration:.1f}s!\n"
        f"  - Setores Censitários:        {n_setores:,}\n"
        f"  - Escolas:                    {n_escolas:,}\n"
        f"  - Acessibilidade Educacional: {n_acessib:,}\n"
        f"  - Estabelecimentos de Saúde:  {n_cnes:,}\n"
        f"  - Malha Viária (OSM):         {n_osm:,}\n"
        f"  - Ocorrências Segurança:      {n_sinesp:,}\n"
        f"  - Cobertura Solo (MapBiomas): {n_mapbiomas:,}\n"
        f"{'='*60}"
    )

    if PREFECT_AVAILABLE:
        create_markdown_artifact(
            key="pipeline-summary-complete",
            markdown=f"""
## RootL Atlas Pipeline — Resumo Completo

| Entidade | Total Carregado |
|:---|:---|
| Setores Censitários | {n_setores:,} |
| Escolas | {n_escolas:,} |
| Acessibilidade Educacional | {n_acessib:,} |
| Estabelecimentos de Saúde (CNES) | {n_cnes:,} |
| Malha Viária (OSM) | {n_osm:,} |
| Ocorrências de Segurança (SINESP) | {n_sinesp:,} |
| Cobertura do Solo (MapBiomas) | {n_mapbiomas:,} |

**Duração total:** {duration:.1f}s | **Concluído em:** {end.isoformat()}
""",
            description="Métricas de execução do pipeline completo",
        )

    return result


def _validate_catalog_and_schemas() -> None:
    """Valida o catálogo e imports de schemas sem executar o pipeline."""
    import yaml
    catalog_path = Path(__file__).parent.parent / "catalog.yaml"
    if not catalog_path.exists():
        raise FileNotFoundError(f"catalog.yaml não encontrado: {catalog_path}")
    with open(catalog_path) as f:
        catalog = yaml.safe_load(f)
    sources = catalog.get("sources", [])
    logger.info(f"  catalog.yaml: {len(sources)} fontes registradas ✓")
    for s in sources:
        logger.info(f"    - {s['id']}: {s['name']}")

    from schemas.setores_schema import SETORES_SILVER_SCHEMA
    from schemas.escolas_schema import ESCOLAS_GOLD_SCHEMA
    logger.info("  Schemas Pandera: importados com sucesso ✓")
    logger.success("dry_run OK — catálogo e schemas válidos")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

app = typer.Typer(name="rootl-atlas-pipeline")


@app.command()
def run(
    ano_censo: int = typer.Option(2024, help="Ano do Censo Escolar INEP"),
    skip_ingest: bool = typer.Option(False, help="Pular download Bronze"),
    dry_run: bool = typer.Option(False, help="Apenas validar sem executar"),
    register_only: bool = typer.Option(False, help="Registrar flows no Prefect sem executar"),
) -> None:
    """Executa o pipeline do RootL Atlas."""
    if register_only:
        logger.info("Registrando flows no Prefect...")
        return

    result = main_pipeline(
        ano_censo=ano_censo,
        skip_ingest=skip_ingest,
        dry_run=dry_run,
    )
    if result.get("status") == "success":
        logger.success("Pipeline executado com sucesso!")
    else:
        logger.info(f"Pipeline finalizado: {result}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        sys.argv.pop(1)
    app()
