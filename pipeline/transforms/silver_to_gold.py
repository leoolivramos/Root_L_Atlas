"""
pipeline/transforms/silver_to_gold.py
========================================
Transformações Silver → Gold (Modelo Canônico Geoespacial).

Esta é a camada qualitativa da plataforma. Vocabulários radicalmente
distintos de diferentes ministérios são mapeados para a ontologia
estrutural comum do RootL Atlas.

Responsabilidades:
- Mapeamento de campos para o modelo canônico
- Validação Pandera (com bloqueio em caso de violações críticas)
- Enriquecimento: join setor censitário por ponto-em-polígono
- Cálculo de métricas de acessibilidade (distância euclidiana — MVP)
- Persistência em Gold GeoParquet com bbox_col
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from loguru import logger
from shapely import get_coordinates

from transforms.geo_utils import (
    MT_BBOX,
    validate_coordinates_in_bbox,
    write_geoparquet_with_bbox,
)


# ─────────────────────────────────────────────────────────────────────────────
# Gold: Setores Censitários
# ─────────────────────────────────────────────────────────────────────────────

# Mapeamento canônico: nome_silver → nome_gold
SETORES_COLUMN_MAP = {
    "cd_setor": "cd_setor",
    "cd_municipio": "cd_municipio",
    "cd_mun": "cd_municipio",
    "nm_municipio": "nm_municipio",
    "nm_mun": "nm_municipio",
    "cd_uf": "cd_uf",
    "sigla": "sg_uf",
    "sg_uf": "sg_uf",
    "cd_dist": "cd_distrito",
    "cd_distrito": "cd_distrito",
    "nm_dist": "nm_distrito",
    "nm_distrito": "nm_distrito",
    "cd_subdist": "cd_subdistrito",
    "nm_subdist": "nm_subdistrito",
    "nm_bairro": "nm_bairro",
    "cd_sit": "tipo_setor",
    "situacao": "nm_tipo_setor",
    "tipo_setor": "tipo_setor",
    "geometry": "geometry",
    "geom": "geometry",
    "centroide": "centroide",
    "area_km2": "area_km2",
    "fonte_id": "fonte_id",
    "versao_processamento": "versao_processamento",
}

TIPO_SETOR_MAP = {
    1: "Urbano — área urbanizada",
    2: "Urbano — área de expansão",
    3: "Urbano — área isolada",
    4: "Rural — vila ou povoado",
    5: "Rural — agrupamento rural",
    6: "Rural — área não agrupada",
    7: "Especial — agrupamento quilombola",
    8: "Especial — terra indígena",
    9: "Especial — outro",
}


def setores_to_gold(
    silver_path: Path,
    gold_path: Path,
) -> Path:
    """
    Transforma setores Silver para o modelo canônico Gold.

    Args:
        silver_path: GeoParquet Silver dos setores
        gold_path: Diretório de saída Gold

    Returns:
        Path do GeoParquet Gold
    """
    from schemas.setores_schema import validate_setores_silver

    logger.info("[Silver→Gold] Processando setores censitários...")
    gdf = gpd.read_parquet(silver_path)

    # Aplica mapeamento canônico
    rename_map = {k: v for k, v in SETORES_COLUMN_MAP.items() if k in gdf.columns}
    gdf = gdf.rename(columns=rename_map)

    # Garante coluna sg_uf
    if "sg_uf" not in gdf.columns:
        gdf["sg_uf"] = "MT"

    # Decodifica tipo_setor
    if "tipo_setor" in gdf.columns:
        gdf["tipo_setor"] = pd.to_numeric(gdf["tipo_setor"], errors="coerce").fillna(1).astype(int)
        if "nm_tipo_setor" not in gdf.columns or gdf["nm_tipo_setor"].isna().all():
            gdf["nm_tipo_setor"] = gdf["tipo_setor"].map(TIPO_SETOR_MAP)

    # Calcula área se não existir
    if "area_km2" not in gdf.columns:
        from transforms.geo_utils import add_area_km2
        gdf = add_area_km2(gdf)

    # Validação Pandera — bloqueia pipeline em caso de falha
    logger.info("  Validando esquema Gold...")
    gdf = validate_setores_silver(gdf)

    # Seleciona e ordena colunas canônicas
    canonical_cols = [
        "cd_setor", "cd_municipio", "nm_municipio", "cd_uf", "sg_uf",
        "cd_distrito", "nm_distrito", "cd_subdistrito", "nm_subdistrito",
        "nm_bairro", "tipo_setor", "nm_tipo_setor",
        "area_km2", "centroide",
        "fonte_id", "versao_processamento",
        "geometry",
    ]
    existing = [c for c in canonical_cols if c in gdf.columns]
    gdf = gdf[existing]

    gold_path.mkdir(parents=True, exist_ok=True)
    output = gold_path / "setores_censitarios.parquet"
    write_geoparquet_with_bbox(gdf, output)

    logger.success(f"[Gold] Setores: {len(gdf):,} registros → {output}")

    # Garante geração da camada de municípios derivada
    mun_output = gold_path / "municipios_mt.parquet"
    if not mun_output.exists():
        generate_municipios_gold(gdf, gold_path)

    return output


def generate_municipios_gold(gdf_setores: gpd.GeoDataFrame, gold_path: Path) -> Path:
    """Gera a malha de municípios de MT a partir da dissolução dos setores censitários."""
    import unicodedata
    logger.info("[Gold] Gerando municípios a partir da dissolução dos setores censitários...")

    mun_gdf = gdf_setores.dissolve(
        by="cd_municipio",
        as_index=False,
        aggfunc={
            "nm_municipio": "first",
            "sg_uf": "first",
            "cd_uf": "first",
        },
    )
    from shapely.geometry import MultiPolygon, Polygon
    mun_gdf["geometry"] = mun_gdf["geometry"].apply(
        lambda g: MultiPolygon([g]) if isinstance(g, Polygon) else g
    )

    def strip_accents(s: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")

    mun_gdf["nm_municipio_ascii"] = mun_gdf["nm_municipio"].apply(strip_accents)
    mun_gdf["nm_uf"] = "Mato Grosso"
    mun_gdf["fonte_id"] = "ibge_censo_2022_setores"
    mun_gdf["versao_processamento"] = "1.0.0"
    mun_gdf["centroide"] = mun_gdf.geometry.centroid

    from transforms.geo_utils import add_area_km2
    mun_gdf = add_area_km2(mun_gdf)

    output = gold_path / "municipios_mt.parquet"
    write_geoparquet_with_bbox(mun_gdf, output)
    logger.success(f"[Gold] Municípios: {len(mun_gdf):,} registros → {output}")
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Gold: Escolas
# ─────────────────────────────────────────────────────────────────────────────

ESCOLAS_COLUMN_MAP = {
    "co_entidade": "co_entidade",
    "no_entidade": "no_entidade",
    "tp_dependencia": "tp_dependencia",
    "tp_situacao_funcionamento": "tp_situacao_funcionamento",
    "co_municipio": "co_municipio",
    "no_municipio": "no_municipio",
    "no_bairro": "no_bairro",
    "in_inf_creche": "in_inf_creche",
    "in_inf_pre_escola": "in_inf_pre_escola",
    "in_fund_ai": "in_fund_anos_iniciais",
    "in_fund_anos_iniciais": "in_fund_anos_iniciais",
    "in_fund_af": "in_fund_anos_finais",
    "in_fund_anos_finais": "in_fund_anos_finais",
    "in_med_regular": "in_medio_regular",
    "in_medio_regular": "in_medio_regular",
    "in_med_medio_integrado": "in_medio_integrado",
    "in_medio_integrado": "in_medio_integrado",
    "in_eja": "in_eja",
    "in_esp_exclusiva": "in_especial_exclusiva",
    "in_laboratorio_informatica": "in_laboratorio_informatica",
    "in_laboratorio_ciencias": "in_laboratorio_ciencias",
    "in_biblioteca": "in_biblioteca",
    "in_quadra_esportes": "in_quadra_esportes",
    "in_acessibilidade_prioritaria": "in_acessibilidade",
    "qt_salas_utilizadas": "qt_salas_utilizadas",
    "qt_equip_computador": "qt_equip_computador",
    "qt_mat_bas": "qt_mat_bas",
    "geometry": "geometry",
    "fonte_id": "fonte_id",
    "versao_processamento": "versao_processamento",
}

TP_DEPENDENCIA_MAP = {
    1: "Federal",
    2: "Estadual",
    3: "Municipal",
    4: "Privada",
}


def escolas_to_gold(
    silver_path: Path,
    gold_path: Path,
    setores_gold_path: Path | None = None,
    ano_censo: int = 2024,
) -> Path:
    """
    Transforma escolas Silver para Gold e realiza join com setor censitário.

    Args:
        silver_path: GeoParquet Silver das escolas
        gold_path: Diretório de saída Gold
        setores_gold_path: GeoParquet Gold dos setores (para sjoin)
        ano_censo: Ano de referência do censo escolar

    Returns:
        Path do GeoParquet Gold
    """
    from schemas.escolas_schema import validate_escolas_silver

    logger.info("[Silver→Gold] Processando escolas...")
    gdf = gpd.read_parquet(silver_path)

    # Mapeamento canônico
    rename_map = {k: v for k, v in ESCOLAS_COLUMN_MAP.items() if k in gdf.columns}
    gdf = gdf.rename(columns=rename_map)

    # Decodifica tp_dependencia
    if "tp_dependencia" in gdf.columns:
        gdf["nm_dependencia"] = gdf["tp_dependencia"].map(TP_DEPENDENCIA_MAP).fillna("Outra")
    else:
        gdf["nm_dependencia"] = "Outra"

    if "tp_situacao_funcionamento" not in gdf.columns:
        gdf["tp_situacao_funcionamento"] = 1
    else:
        gdf["tp_situacao_funcionamento"] = gdf["tp_situacao_funcionamento"].fillna(1).astype(int)

    # Adiciona ano_censo
    gdf["ano_censo"] = ano_censo

    # Converte booleanas (INEP usa 0/1 ou S/N)
    bool_cols = [c for c in gdf.columns if c.startswith("in_")]
    for col in bool_cols:
        if col in gdf.columns:
            if gdf[col].dtype == object:
                gdf[col] = gdf[col].map({"S": True, "N": False, "1": True, "0": False})
            else:
                gdf[col] = gdf[col].astype(bool)

    # Validação Pandera
    logger.info("  Validando esquema escolas Gold...")
    gdf = validate_escolas_silver(gdf)

    # Spatial join: associa cada escola ao setor censitário que a contém
    if setores_gold_path and setores_gold_path.exists():
        logger.info("  Spatial join: escola → setor censitário...")
        setores = gpd.read_parquet(
            setores_gold_path,
            columns=["cd_setor", "geometry"],
        )
        joined = gpd.sjoin(
            gdf[["co_entidade", "geometry"]],
            setores[["cd_setor", "geometry"]],
            how="left",
            predicate="within",
        )
        # Adiciona cd_setor ao GDF principal
        cd_setor_map = joined.set_index("co_entidade")["cd_setor"].to_dict()
        gdf["cd_setor_ref"] = gdf["co_entidade"].map(cd_setor_map)
        matched = gdf["cd_setor_ref"].notna().sum()
        logger.info(f"  {matched:,}/{len(gdf):,} escolas associadas a um setor")

    gold_path.mkdir(parents=True, exist_ok=True)
    output = gold_path / "escolas.parquet"
    write_geoparquet_with_bbox(gdf, output)

    logger.success(f"[Gold] Escolas: {len(gdf):,} registros → {output}")
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Gold: Acessibilidade Educacional (distância euclidiana — MVP)
# ─────────────────────────────────────────────────────────────────────────────


def compute_accessibility_euclidean(
    setores_gold_path: Path,
    escolas_gold_path: Path,
    gold_path: Path,
) -> Path:
    """
    Calcula métricas de acessibilidade educacional (fase MVP).

    Método: distância euclidiana do centróide do setor à escola mais próxima.

    NOTA METODOLÓGICA: Distância euclidiana (linha reta) é uma estimativa
    conservadora. Fase 2 substituirá pelo tempo de viagem via rede viária
    (OSRM/Valhalla). Todos os resultados incluem aviso metodológico.

    Args:
        setores_gold_path: GeoParquet dos setores (com centróides)
        escolas_gold_path: GeoParquet das escolas
        gold_path: Diretório de saída Gold

    Returns:
        Path do Parquet de acessibilidade
    """
    logger.info("[Gold] Calculando acessibilidade educacional (euclidiana)...")

    setores = gpd.read_parquet(
        setores_gold_path,
        columns=["cd_setor", "centroide"],
    )
    escolas = gpd.read_parquet(
        escolas_gold_path,
        columns=["co_entidade", "tp_dependencia", "in_fund_anos_iniciais",
                 "in_fund_anos_finais", "geometry"],
    )

    # Usa centróide como geometria do setor
    setores = setores.set_geometry("centroide")

    # Projeta para coordenadas métricas para cálculo de distância
    EPSG_METRIC = 5880  # SIRGAS 2000 / Brazil Polyconic
    setores_m = setores.to_crs(epsg=EPSG_METRIC)
    escolas_m = escolas.to_crs(epsg=EPSG_METRIC)

    # Subconjunto: escolas públicas de ensino fundamental
    escolas_fund_pub = escolas_m[
        (escolas_m["tp_dependencia"].isin([1, 2, 3])) &
        (
            escolas_m["in_fund_anos_iniciais"].fillna(False) |
            escolas_m["in_fund_anos_finais"].fillna(False)
        )
    ]

    logger.info(
        f"  {len(setores):,} setores | "
        f"{len(escolas):,} escolas totais | "
        f"{len(escolas_fund_pub):,} escolas fund. públicas"
    )

    records = []
    escola_coords = np.array([
        [g.x, g.y] for g in escolas_m.geometry
    ])
    fund_pub_coords = np.array([
        [g.x, g.y] for g in escolas_fund_pub.geometry
    ]) if len(escolas_fund_pub) > 0 else None

    setor_centroids = [g for g in setores_m.geometry]
    setor_cds = setores_m["cd_setor"].tolist()

    for cd_setor, centroid in zip(setor_cds, setor_centroids):
        cx, cy = centroid.x, centroid.y

        # Distância para TODAS as escolas
        dists = np.sqrt((escola_coords[:, 0] - cx)**2 + (escola_coords[:, 1] - cy)**2)
        idx_prox = int(np.argmin(dists))
        dist_km = float(dists[idx_prox]) / 1000.0
        co_prox = int(escolas_m.iloc[idx_prox]["co_entidade"])

        # Escolas num raio de 5km e 10km
        qt_5km = int(np.sum(dists <= 5_000))
        qt_10km = int(np.sum(dists <= 10_000))

        # Escola pública fundamental mais próxima
        dist_fund_km = None
        co_fund_prox = None
        if fund_pub_coords is not None and len(fund_pub_coords) > 0:
            dists_fund = np.sqrt(
                (fund_pub_coords[:, 0] - cx)**2 + (fund_pub_coords[:, 1] - cy)**2
            )
            idx_f = int(np.argmin(dists_fund))
            dist_fund_km = float(dists_fund[idx_f]) / 1000.0
            co_fund_prox = int(escolas_fund_pub.iloc[idx_f]["co_entidade"])

        # Escolas públicas dentro de 5km
        qt_pub_5km = 0
        if fund_pub_coords is not None and len(fund_pub_coords) > 0:
            qt_pub_5km = int(np.sum(dists_fund <= 5_000))

        records.append({
            "cd_setor": cd_setor,
            "co_entidade_mais_proxima": co_prox,
            "distancia_eucl_km": round(dist_km, 3),
            "co_entidade_fund_prox": co_fund_prox,
            "dist_fund_eucl_km": round(dist_fund_km, 3) if dist_fund_km else None,
            "qt_escolas_5km": qt_5km,
            "qt_escolas_10km": qt_10km,
            "qt_escolas_publicas_5km": qt_pub_5km,
            "metodo_calculo": "distancia_euclidiana",
            "nota_metodologica": (
                "Distância euclidiana (linha reta). Estimativa conservadora. "
                "Fase 2 substituirá por tempo de viagem via rede viária (OSRM/Valhalla)."
            ),
        })

    df = pd.DataFrame(records)

    gold_path.mkdir(parents=True, exist_ok=True)
    output = gold_path / "acessibilidade_educacional.parquet"
    df.to_parquet(output, index=False, compression="snappy")

    logger.success(
        f"[Gold] Acessibilidade: {len(df):,} setores processados → {output}"
    )
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Gold: Estabelecimentos de Saúde (CNES)
# ─────────────────────────────────────────────────────────────────────────────

TP_UNIDADE_SAUDE_MAP = {
    1: "Posto de Saúde",
    2: "Centro de Saúde / UBS",
    4: "Policlínica",
    5: "Hospital Geral",
    7: "Hospital Especializado",
    15: "Unidade Mista",
    20: "Pronto Socorro Geral",
    21: "Pronto Socorro Especializado",
    22: "Consultório",
    36: "Clínica Especializada",
    39: "Apoio Diagnóstico e Terapia",
    42: "Unidade Móvel",
    73: "Pronto Atendimento",
}


def cnes_to_gold(
    silver_path: Path,
    gold_path: Path,
    setores_gold_path: Path | None = None,
) -> Path:
    """Transforma estabelecimentos de saúde Silver para modelo canônico Gold."""
    logger.info("[Silver→Gold] Processando estabelecimentos de saúde...")
    gdf = gpd.read_parquet(silver_path)

    # Normaliza tipos
    if "tp_unid" in gdf.columns and "tp_unidade" not in gdf.columns:
        gdf["tp_unidade"] = pd.to_numeric(gdf["tp_unid"], errors="coerce").fillna(0).astype(int)
    elif "tp_unidade" in gdf.columns:
        gdf["tp_unidade"] = pd.to_numeric(gdf["tp_unidade"], errors="coerce").fillna(0).astype(int)

    gdf["nm_tp_unidade"] = gdf["tp_unidade"].map(TP_UNIDADE_SAUDE_MAP).fillna("Estabelecimento de Saúde")

    if "tp_gestao" not in gdf.columns:
        gdf["tp_gestao"] = gdf.get("tpgestao", "M").astype(str).str.strip().str[:1]

    if "no_fantasia" not in gdf.columns:
        gdf["no_fantasia"] = gdf.get("nofantas", gdf.get("no_razao_social", "Estabelecimento de Saúde"))

    if "no_razao_social" not in gdf.columns:
        gdf["no_razao_social"] = gdf.get("norazao", gdf["no_fantasia"])

    # Leitos
    leito_col = "leithosp" if "leithosp" in gdf.columns else "qt_leitos_total"
    if leito_col in gdf.columns:
        gdf["qt_leitos_total"] = pd.to_numeric(gdf[leito_col], errors="coerce").fillna(0).astype(int)
    else:
        gdf["qt_leitos_total"] = 0

    gdf["qt_leitos_sus"] = gdf["qt_leitos_total"]
    gdf["qt_leitos_nao_sus"] = 0

    # Spatial join: setor censitário
    if setores_gold_path and setores_gold_path.exists():
        logger.info("  Spatial join: saúde → setor censitário...")
        setores = gpd.read_parquet(setores_gold_path, columns=["cd_setor", "geometry"])
        joined = gpd.sjoin(
            gdf[["co_cnes", "geometry"]],
            setores[["cd_setor", "geometry"]],
            how="left",
            predicate="within",
        )
        cd_setor_map = joined.set_index("co_cnes")["cd_setor"].to_dict()
        gdf["cd_setor_ref"] = gdf["co_cnes"].map(cd_setor_map)

    gold_path.mkdir(parents=True, exist_ok=True)
    output = gold_path / "estabelecimentos_saude.parquet"
    write_geoparquet_with_bbox(gdf, output)
    logger.success(f"[Gold] Estabelecimentos de saúde: {len(gdf):,} registros → {output}")
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Gold: Malha Viária OSM
# ─────────────────────────────────────────────────────────────────────────────

def osm_to_gold(
    silver_path: Path,
    gold_path: Path,
) -> Path:
    """Transforma malha viária Silver para Gold."""
    logger.info("[Silver→Gold] Processando malha viária OSM...")
    gdf = gpd.read_parquet(silver_path)

    # Garante colunas esperadas pelo PostGIS
    if "osm_id" not in gdf.columns:
        gdf["osm_id"] = np.arange(1, len(gdf) + 1, dtype=int)
    gdf["osm_id"] = gdf["osm_id"].astype(int)

    gold_path.mkdir(parents=True, exist_ok=True)
    output = gold_path / "malha_viaria_osm.parquet"
    write_geoparquet_with_bbox(gdf, output)
    logger.success(f"[Gold] Malha viária: {len(gdf):,} registros → {output}")
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Gold: SINESP Ocorrências de Segurança
# ─────────────────────────────────────────────────────────────────────────────

def sinesp_to_gold(
    silver_path: Path,
    gold_path: Path,
    municipios_gold_path: Path | None = None,
) -> Path:
    """
    Transforma ocorrências SINESP Silver para Gold.
    Herda a geometria municipal (resolução honesta máxima).
    """
    logger.info("[Silver→Gold] Processando ocorrências de segurança...")
    df = pd.read_parquet(silver_path)

    if municipios_gold_path and municipios_gold_path.exists():
        from shapely.geometry import MultiPolygon, Polygon
        mun_gdf = gpd.read_parquet(municipios_gold_path, columns=["cd_municipio", "geometry"])
        def _to_multi(g):
            if isinstance(g, Polygon):
                return MultiPolygon([g])
            return g
        mun_geom_map = mun_gdf.set_index("cd_municipio")["geometry"].apply(_to_multi).to_dict()
        df["geometry"] = df["co_municipio"].astype(str).map(mun_geom_map)
        gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    else:
        gdf = gpd.GeoDataFrame(df)

    gold_path.mkdir(parents=True, exist_ok=True)
    output = gold_path / "ocorrencias_seguranca.parquet"
    if "geometry" in gdf.columns and gdf.geometry.notna().any():
        write_geoparquet_with_bbox(gdf, output)
    else:
        gdf.to_parquet(output, index=False, compression="snappy")

    logger.success(f"[Gold] Ocorrências segurança: {len(gdf):,} registros → {output}")
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Gold: MapBiomas Cobertura do Solo
# ─────────────────────────────────────────────────────────────────────────────

def mapbiomas_to_gold(
    silver_path: Path,
    gold_path: Path,
) -> Path:
    """Transforma dados de cobertura do solo Silver para Gold."""
    logger.info("[Silver→Gold] Processando cobertura do solo MapBiomas...")
    df = pd.read_parquet(silver_path)

    gold_path.mkdir(parents=True, exist_ok=True)
    output = gold_path / "cobertura_solo_mapbiomas.parquet"
    df.to_parquet(output, index=False, compression="snappy")
    logger.success(f"[Gold] Cobertura do solo: {len(df):,} registros → {output}")
    return output

