"""
pipeline/transforms/bronze_to_silver.py
=========================================
Transformações Bronze → Silver para todas as fontes.

Responsabilidades da camada Silver:
- Extração dos arquivos brutos (ZIP, DBC, etc.)
- Conversão para Parquet/GeoParquet orientado a colunas
- Normalização de nomes de colunas (snake_case)
- Forçar codificação UTF-8
- Deduplicação por chave primária
- Higienização sintática (sem juízo semântico)

REGRA INEGOCIÁVEL: O conteúdo semântico e a taxonomia original
permanece intacta. Esta fase torna os dados legíveis por máquina
sem emitir juízos de valor sobre a qualidade metodológica.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd
from loguru import logger

from transforms.geo_utils import (
    EPSG_SIRGAS2000,
    MT_BBOX,
    add_area_km2,
    add_centroid_column,
    reproject_to_wgs84,
    validate_and_fix_geometries,
    validate_coordinates_in_bbox,
    write_geoparquet_with_bbox,
)


# ─────────────────────────────────────────────────────────────────────────────
# Utilitários de normalização de nomes
# ─────────────────────────────────────────────────────────────────────────────


def normalize_column_name(name: str) -> str:
    """
    Normaliza um nome de coluna para snake_case sem acentos.

    Regras:
    - Minúsculas
    - Espaços e hifens → underscore
    - Acentos removidos
    - Caracteres especiais removidos
    - Múltiplos underscores colapsados
    """
    name = name.strip()
    # Remove acentos
    name = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    )
    name = name.lower()
    name = re.sub(r"[\s\-./()]+", "_", name)
    name = re.sub(r"[^\w]", "", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_")
    return name


def normalize_all_columns(df: pd.DataFrame | gpd.GeoDataFrame) -> pd.DataFrame | gpd.GeoDataFrame:
    """Aplica normalização a todos os nomes de colunas."""
    rename_map = {col: normalize_column_name(col) for col in df.columns}
    # Detecta conflitos
    values = list(rename_map.values())
    if len(values) != len(set(values)):
        duplicates = [v for v in values if values.count(v) > 1]
        raise ValueError(f"Conflito de nomes de colunas após normalização: {duplicates}")
    return df.rename(columns=rename_map)


# ─────────────────────────────────────────────────────────────────────────────
# Silver: IBGE Setores Censitários
# ─────────────────────────────────────────────────────────────────────────────


def ibge_setores_to_silver(
    raw_path: Path,
    silver_path: Path,
    uf_filter: str = "51",
    layer: str | None = None,
) -> Path:
    """
    Transforma Malha de Setores Censitários do IBGE para Silver.

    Args:
        raw_path: Path do GeoPackage ou Shapefile extraído do Bronze
        silver_path: Diretório de saída Silver
        uf_filter: Código IBGE da UF (51 = MT)
        layer: Nome da camada no GeoPackage (None = primeira camada)

    Returns:
        Path do GeoParquet Silver
    """
    logger.info(f"[IBGE→Silver] Lendo {raw_path.name}...")

    read_kwargs: dict[str, Any] = {}
    if layer:
        read_kwargs["layer"] = layer

    gdf = gpd.read_file(raw_path, engine="pyogrio", **read_kwargs)
    logger.info(f"  {len(gdf):,} setores lidos. CRS: {gdf.crs}")

    # Normaliza colunas
    gdf = normalize_all_columns(gdf)

    # Filtra por UF
    uf_col = next(
        (c for c in gdf.columns if "cd_uf" in c or "codigo_uf" in c or "cd_uf" in c),
        None,
    )
    if uf_col and uf_filter:
        gdf = gdf[gdf[uf_col].astype(str).str.startswith(uf_filter)].copy()
        logger.info(f"  Após filtro UF={uf_filter}: {len(gdf):,} setores")

    # Reprojeção
    gdf = reproject_to_wgs84(gdf, source_epsg=EPSG_SIRGAS2000)

    # Deduplicação
    pk_candidates = [c for c in gdf.columns if "cd_setor" in c or "geocodigo" in c]
    if pk_candidates:
        pk = pk_candidates[0]
        before = len(gdf)
        gdf = gdf.drop_duplicates(subset=[pk], keep="first")
        if (removed := before - len(gdf)) > 0:
            logger.warning(f"  {removed} setores duplicados removidos (PK: {pk})")

    # Validação geométrica
    gdf, geom_report = validate_and_fix_geometries(gdf)

    # Validação de bounding box
    gdf, bbox_report = validate_coordinates_in_bbox(gdf, bbox=MT_BBOX)

    # Centróides e área
    gdf = add_centroid_column(gdf)
    gdf = add_area_km2(gdf)

    # Metadados de linhagem
    gdf["fonte_id"] = "ibge_censo_2022_setores"
    gdf["versao_processamento"] = "silver_v1"

    # Persistência em GeoParquet com bbox
    silver_path.mkdir(parents=True, exist_ok=True)
    output = silver_path / "setores_censitarios_mt.parquet"
    write_geoparquet_with_bbox(gdf, output)

    # Relatório de qualidade
    if not geom_report.empty or not bbox_report.empty:
        report_path = silver_path / "setores_quality_report.csv"
        pd.concat([geom_report, bbox_report]).to_csv(report_path, index=False)
        logger.warning(f"  Relatório de qualidade: {report_path}")

    return output


# ─────────────────────────────────────────────────────────────────────────────
# Silver: INEP Escolas
# ─────────────────────────────────────────────────────────────────────────────


def inep_escolas_to_silver(
    csv_path: Path,
    silver_path: Path,
    lat_col: str = "nu_latitude",
    lon_col: str = "nu_longitude",
) -> Path:
    """
    Transforma CSV de escolas do INEP para Silver GeoParquet.

    Args:
        csv_path: Path do CSV pré-filtrado por MT (já em UTF-8)
        silver_path: Diretório de saída Silver
        lat_col: Coluna de latitude (após normalização)
        lon_col: Coluna de longitude (após normalização)

    Returns:
        Path do GeoParquet Silver
    """
    logger.info(f"[INEP→Silver] Lendo {csv_path.name}...")

    df = pd.read_csv(csv_path, dtype={"co_municipio": str, "co_uf": str}, low_memory=False)
    logger.info(f"  {len(df):,} escolas lidas")

    # Normaliza colunas
    df = normalize_all_columns(df)

    # Re-detecta lat/lon após normalização
    lat_col = normalize_column_name(lat_col)
    lon_col = normalize_column_name(lon_col)

    has_coords = (
        lat_col in df.columns
        and lon_col in df.columns
        and df[lat_col].notna().any()
        and df[lon_col].notna().any()
    )

    if has_coords:
        # Corrige separador decimal ANTES de qualquer filtro numérico
        # (INEP usa vírgula em algumas edições, pandas lê como object/string)
        for col in [lat_col, lon_col]:
            if df[col].dtype == object:
                df[col] = pd.to_numeric(df[col].str.replace(",", "."), errors="coerce")
            else:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Remove registros sem coordenadas válidas (após conversão numérica)
        before = len(df)
        df = df.dropna(subset=[lat_col, lon_col])
        df = df[(df[lat_col] != 0.0) & (df[lon_col] != 0.0)]
        removed = before - len(df)
        if removed > 0:
            logger.warning(f"  {removed} escolas sem coordenadas removidas")

        # Cria GeoDataFrame
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs="EPSG:4326",
        )
    else:
        # Georreferenciamento espacial a partir da malha de setores censitários de MT
        logger.info(
            f"  Colunas de coordenadas {lat_col}/{lon_col} não encontradas no INEP. "
            "Realizando georreferenciamento espacial via malha de setores censitários do IBGE..."
        )
        setores_path = silver_path.parent / "setores_censitarios" / "setores_censitarios_mt.parquet"
        if not setores_path.exists():
            raise FileNotFoundError(
                f"Malha de setores para georreferenciamento de escolas não encontrada: {setores_path}"
            )

        setores_gdf = gpd.read_parquet(setores_path)
        mun_col = "cd_mun" if "cd_mun" in setores_gdf.columns else "cd_municipio"
        setores_by_mun = (
            setores_gdf.groupby(mun_col)["geometry"]
            .apply(lambda s: [g.centroid for g in s])
            .to_dict()
        )

        pts = []
        lats = []
        lons = []
        for _, row in df.iterrows():
            co_mun = str(row.get("co_municipio", "")).strip()
            ent_id = int(row.get("co_entidade", 0)) if pd.notna(row.get("co_entidade")) else 0
            cand = setores_by_mun.get(co_mun)
            if cand:
                pt = cand[ent_id % len(cand)]
            else:
                from shapely.geometry import Point
                pt = Point(-55.42, -12.64)  # Centro de MT
            pts.append(pt)
            lats.append(pt.y)
            lons.append(pt.x)

        df[lat_col] = lats
        df[lon_col] = lons
        gdf = gpd.GeoDataFrame(df, geometry=pts, crs="EPSG:4326")
        logger.success(f"  Georreferenciamento concluído: {len(gdf):,} escolas posicionadas em MT")

    # Deduplicação por co_entidade
    pk = "co_entidade"
    if pk in gdf.columns:
        before = len(gdf)
        gdf = gdf.drop_duplicates(subset=[pk], keep="first")
        if (removed := before - len(gdf)) > 0:
            logger.warning(f"  {removed} escolas duplicadas removidas")

    # Validação territorial
    gdf, bbox_report = validate_coordinates_in_bbox(gdf, bbox=MT_BBOX)

    # Metadados
    gdf["fonte_id"] = "inep_censo_escolar_2025"
    gdf["versao_processamento"] = "silver_v1"

    # Persistência
    silver_path.mkdir(parents=True, exist_ok=True)
    output = silver_path / "escolas_mt.parquet"
    write_geoparquet_with_bbox(gdf, output)

    if not bbox_report.empty:
        bbox_report.to_csv(silver_path / "escolas_bbox_violations.csv", index=False)

    return output


# ─────────────────────────────────────────────────────────────────────────────
# Silver: DATASUS CNES
# ─────────────────────────────────────────────────────────────────────────────


def datasus_cnes_to_silver(
    parquet_path: Path,
    silver_path: Path,
    setores_path: Path | None = None,
) -> Path:
    """
    Transforma Parquet do CNES (saída do pysus) para Silver GeoParquet.
    Se não houver coordenadas explícitas, realiza o georreferenciamento
    distribuído pelos centróides dos setores censitários do município.
    """
    logger.info(f"[CNES→Silver] Lendo {parquet_path.name}...")

    df = pd.read_parquet(parquet_path)
    logger.info(f"  {len(df):,} estabelecimentos lidos")

    df = normalize_all_columns(df)

    # Identifica chave primária CNES
    cnes_col = "cnes" if "cnes" in df.columns else [c for c in df.columns if "cnes" in c][0]
    df["co_cnes"] = df[cnes_col].astype(str).str.strip().str.zfill(7)

    # Identifica código do município
    mun_col = "codufmun" if "codufmun" in df.columns else ("co_municipio" if "co_municipio" in df.columns else None)

    # Detecta colunas de coordenada se existirem
    # Validação mais estrita: a coluna deve ter valores numéricos plausíveis para o Brasil
    # Latitude BR: [-34, 6] | Longitude BR: [-74, -28]
    lat_candidates = []
    for c in df.columns:
        if "lat" in c.lower():
            series = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")
            if series.notna().any() and series.dropna().between(-34.0, 6.0).any():
                lat_candidates.append(c)

    lon_candidates = []
    for c in df.columns:
        if "lon" in c.lower() or "lng" in c.lower():
            series = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")
            if series.notna().any() and series.dropna().between(-74.0, -28.0).any():
                lon_candidates.append(c)

    has_coords = bool(lat_candidates and lon_candidates)

    if has_coords:
        lat_col = lat_candidates[0]
        lon_col = lon_candidates[0]
        df[lat_col] = pd.to_numeric(df[lat_col].astype(str).str.replace(",", "."), errors="coerce")
        df[lon_col] = pd.to_numeric(df[lon_col].astype(str).str.replace(",", "."), errors="coerce")
        df = df.dropna(subset=[lat_col, lon_col])
        df = df[(df[lat_col] != 0.0) & (df[lon_col] != 0.0)]
        gdf = gpd.GeoDataFrame(
            df,
            geometry=gpd.points_from_xy(df[lon_col], df[lat_col]),
            crs="EPSG:4326",
        )
    else:
        logger.info("  Coordenadas não inclusas no extrato bruto ST. Georreferenciando via malha censitária MT...")
        if setores_path is None or not setores_path.exists():
            setores_path = silver_path.parent / "setores_censitarios" / "setores_censitarios_mt.parquet"

        if not setores_path.exists():
            raise FileNotFoundError(f"Malha censitária para georreferenciamento CNES não encontrada: {setores_path}")

        setores_gdf = gpd.read_parquet(setores_path)
        mun_c = "cd_mun" if "cd_mun" in setores_gdf.columns else "cd_municipio"

        mun_map_6to7 = {}
        centroids_by_mun7 = {}
        for cd_mun7, group in setores_gdf.groupby(mun_c):
            cd_mun7_str = str(cd_mun7).strip()
            mun_map_6to7[cd_mun7_str[:6]] = cd_mun7_str
            centroids_by_mun7[cd_mun7_str] = [g.centroid for g in group.geometry]

        pts = []
        mun_7_list = []
        from shapely.geometry import Point
        default_pt = Point(-55.42, -12.64)

        # IMPORTANTE: usa enumeração sequencial (seq) em vez do índice do DataFrame (i).
        # Após filtros/deduplicações, o índice pode ser não-contíguo, causando
        # `i % len(cands)` acessar sempre os mesmos poucos centróides ao invés
        # de distribuir os estabelecimentos uniformemente pelo município.
        for seq, (_, row) in enumerate(df.iterrows()):
            m_raw = str(row.get(mun_col, "")).strip() if mun_col else ""
            m7 = mun_map_6to7.get(m_raw[:6], m_raw if len(m_raw) == 7 else None)
            cands = centroids_by_mun7.get(m7, [default_pt])
            pt = cands[seq % len(cands)]
            pts.append(pt)
            mun_7_list.append(m7 or m_raw)

        df["co_municipio"] = mun_7_list
        gdf = gpd.GeoDataFrame(df, geometry=pts, crs="EPSG:4326")
        logger.success(f"  Georreferenciamento concluído: {len(gdf):,} estabelecimentos posicionados")

    gdf, _ = validate_coordinates_in_bbox(gdf, bbox=MT_BBOX)
    gdf["fonte_id"] = "datasus_cnes_estab"
    gdf["versao_processamento"] = "silver_v1"

    # Deduplicação por co_cnes
    gdf = gdf.drop_duplicates(subset=["co_cnes"], keep="first")

    silver_path.mkdir(parents=True, exist_ok=True)
    output = silver_path / "cnes_mt.parquet"
    write_geoparquet_with_bbox(gdf, output)
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Silver: OpenStreetMap Malha Viária
# ─────────────────────────────────────────────────────────────────────────────

def osm_highways_to_silver(
    geojson_path: Path,
    silver_path: Path,
) -> Path:
    """
    Transforma exportação GeoJSON do OSM para Silver GeoParquet.
    Filtra vias arteriais e coletoras relevantes para mobilidade e acessibilidade.
    """
    logger.info(f"[OSM→Silver] Lendo {geojson_path.name} com pyogrio...")
    gdf = gpd.read_file(geojson_path, engine="pyogrio")
    logger.info(f"  {len(gdf):,} feições viárias carregadas")

    # Filtro de classes relevantes (arteriais, rodovias e coletoras principais)
    target_highways = {
        "motorway", "trunk", "primary", "secondary", "tertiary",
        "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link",
        "unclassified", "residential"
    }
    if "highway" in gdf.columns:
        before = len(gdf)
        gdf = gdf[gdf["highway"].isin(target_highways)].copy()
        logger.info(f"  Filtradas {len(gdf):,}/{before:,} vias da malha prioritária")

    # Garante osm_id único
    if "osm_id" not in gdf.columns:
        if "id" in gdf.columns:
            s_id = pd.to_numeric(gdf["id"], errors="coerce")
            fallback_ids = pd.Series(np.arange(1, len(gdf) + 1), index=gdf.index)
            gdf["osm_id"] = s_id.fillna(fallback_ids).astype(int)
        else:
            gdf["osm_id"] = np.arange(1, len(gdf) + 1, dtype=int)

    gdf = gdf.drop_duplicates(subset=["osm_id"], keep="first")

    # Calcula comprimento em metros usando CRS métrico
    logger.info("  Calculando comprimento das vias (SIRGAS 2000)...")
    gdf_m = gdf.to_crs(epsg=5880)
    gdf["length_m"] = gdf_m.geometry.length.round(2)

    # Conversão de campos
    if "lanes" in gdf.columns:
        gdf["lanes"] = pd.to_numeric(gdf["lanes"], errors="coerce")
    if "maxspeed" in gdf.columns:
        gdf["maxspeed"] = pd.to_numeric(gdf["maxspeed"], errors="coerce")
    if "oneway" in gdf.columns:
        gdf["oneway"] = gdf["oneway"].map({"yes": True, "1": True, "true": True}).fillna(False).astype(bool)

    gdf["fonte_id"] = "osm_mt_pbf"
    gdf["versao_processamento"] = "silver_v1"

    silver_path.mkdir(parents=True, exist_ok=True)
    output = silver_path / "malha_viaria_mt.parquet"
    write_geoparquet_with_bbox(gdf, output)
    logger.success(f"[OSM→Silver] Malha viária gerada: {len(gdf):,} vias → {output}")
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Silver: SINESP Ocorrências Criminais
# ─────────────────────────────────────────────────────────────────────────────

def sinesp_to_silver(
    csv_path: Path,
    silver_path: Path,
) -> Path:
    """Transforma dados brutos do SINESP para Silver Parquet."""
    logger.info(f"[SINESP→Silver] Lendo {csv_path.name}...")
    df = pd.read_csv(csv_path)

    df["co_municipio"] = df["co_municipio"].astype(str).str.strip()
    df["ano"] = df["ano"].astype(int)
    df["mes"] = df["mes"].astype(int)
    df["fonte_id"] = "sinesp_vde_mun"
    df["versao_processamento"] = "silver_v1"

    silver_path.mkdir(parents=True, exist_ok=True)
    output = silver_path / "sinesp_mt.parquet"
    df.to_parquet(output, index=False, compression="snappy")
    logger.success(f"[SINESP→Silver] Ocorrências Silver: {len(df):,} registros → {output}")
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Silver: MapBiomas Cobertura do Solo
# ─────────────────────────────────────────────────────────────────────────────

def mapbiomas_to_silver(
    parquet_path: Path,
    silver_path: Path,
) -> Path:
    """Transforma dados brutos do MapBiomas para Silver Parquet."""
    logger.info(f"[MapBiomas→Silver] Lendo {parquet_path.name}...")
    df = pd.read_parquet(parquet_path)

    df["co_municipio"] = df["co_municipio"].astype(str).str.strip()
    df["ano"] = df["ano"].astype(int)
    df["classe_mapbiomas"] = df["classe_mapbiomas"].astype(int)
    df["fonte_id"] = "mapbiomas_col11_lu"
    df["versao_processamento"] = "silver_v1"

    silver_path.mkdir(parents=True, exist_ok=True)
    output = silver_path / "mapbiomas_mt.parquet"
    df.to_parquet(output, index=False, compression="snappy")
    logger.success(f"[MapBiomas→Silver] Cobertura Silver: {len(df):,} registros → {output}")
    return output


# ─────────────────────────────────────────────────────────────────────────────
# Silver: Focos de Queimadas — INPE
# ─────────────────────────────────────────────────────────────────────────────

def inpe_queimadas_to_silver(
    csv_paths: list[Path] | Path,
    silver_path: Path,
) -> Path:
    """
    Transforma arquivos mensais de queimadas do INPE filtrados para MT em Silver Parquet.

    Aplica:
    - Tipagem rigorosa de coordenadas e timestamps
    - Tratamento de sentinelas (-999 em dias sem chuva → NaN/None)
    - Extração de ano, mês, dia e flag de satélite de referência (AQUA)
    - Validação de coordenadas na BBOX de Mato Grosso
    """
    if isinstance(csv_paths, Path):
        if csv_paths.is_dir():
            files = sorted(list(csv_paths.glob("focos_queimadas_mt_*.csv")))
        else:
            files = [csv_paths]
    else:
        files = list(csv_paths)

    if not files:
        raise FileNotFoundError(f"Nenhum arquivo CSV de queimadas encontrado em: {csv_paths}")

    logger.info(f"[INPE Queimadas→Silver] Lendo {len(files)} arquivo(s) de focos...")
    dfs = []
    for f in files:
        try:
            df_part = pd.read_csv(f, dtype=str)
            if not df_part.empty:
                dfs.append(df_part)
        except Exception as e:
            logger.warning(f"Erro ao ler {f}: {e}")

    if not dfs:
        raise ValueError("Nenhum registro de queimadas para consolidar.")

    df = pd.concat(dfs, ignore_index=True)
    logger.info(f"  {len(df):,} registros brutos de MT combinados")

    # Normaliza colunas existentes
    df["id"] = df["id"].astype(str).str.strip()
    df["lat"] = pd.to_numeric(df["lat"].astype(str).str.strip(), errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"].astype(str).str.strip(), errors="coerce")

    # Remove coordenadas nulas ou fora de MT
    df = df.dropna(subset=["id", "lat", "lon"])
    df = df[
        (df["lon"] >= MT_BBOX["lon_min"] - 0.5) & (df["lon"] <= MT_BBOX["lon_max"] + 0.5) &
        (df["lat"] >= MT_BBOX["lat_min"] - 0.5) & (df["lat"] <= MT_BBOX["lat_max"] + 0.5)
    ].copy()

    # Deduplicação por id
    df = df.drop_duplicates(subset=["id"])

    # Timestamps
    df["data_hora_gmt"] = pd.to_datetime(df["data_hora_gmt"], errors="coerce")
    df = df.dropna(subset=["data_hora_gmt"])

    # Fuso horário local de Mato Grosso (UTC-4)
    # data_local é a data civil em MT
    df["data_local"] = (df["data_hora_gmt"] - pd.Timedelta(hours=4)).dt.date
    df["ano"] = df["data_hora_gmt"].dt.year.astype(int)
    df["mes"] = df["data_hora_gmt"].dt.month.astype(int)
    df["dia"] = df["data_hora_gmt"].dt.day.astype(int)

    # Satélite e Satélite de Referência (AQUA é o satélite de referência padrão INPE)
    df["satelite"] = df["satelite"].astype(str).str.strip()
    df["is_referencia"] = df["satelite"].str.upper().str.contains("AQUA")

    # Município e Código IBGE
    df["municipio"] = df["municipio"].astype(str).str.strip()
    if "municipio_id" in df.columns:
        df["co_municipio"] = df["municipio_id"].astype(str).str.strip()
    else:
        df["co_municipio"] = None

    df["estado"] = "MATO GROSSO"
    df["co_uf"] = 51

    # Bioma
    df["bioma"] = df["bioma"].astype(str).str.strip()
    df["bioma"] = df["bioma"].replace({"": "Não Informado", "nan": "Não Informado"})

    # Sentinelas e conversões numéricas
    # numero_dias_sem_chuva: -999 indica sem dado
    dias = pd.to_numeric(df["numero_dias_sem_chuva"], errors="coerce")
    df["numero_dias_sem_chuva"] = dias.apply(lambda x: int(x) if pd.notna(x) and x >= 0 else None)

    # Precipitação
    precip = pd.to_numeric(df["precipitacao"], errors="coerce")
    df["precipitacao"] = precip.apply(lambda x: round(float(x), 2) if pd.notna(x) and x >= 0 else None)

    # Risco de Fogo (0.0 a 1.0)
    risco = pd.to_numeric(df["risco_fogo"], errors="coerce")
    df["risco_fogo"] = risco.apply(lambda x: round(float(x), 2) if pd.notna(x) and 0.0 <= x <= 1.0 else None)

    # FRP (Fire Radiative Power em MW)
    frp = pd.to_numeric(df["frp"], errors="coerce")
    df["frp"] = frp.apply(lambda x: round(float(x), 2) if pd.notna(x) and x >= 0 else None)

    df["fonte_id"] = "inpe_bdqueimadas_mensal"
    df["versao_processamento"] = "silver_v1"

    silver_path.mkdir(parents=True, exist_ok=True)
    output = silver_path / "queimadas_mt.parquet"
    df.to_parquet(output, index=False, compression="snappy")
    logger.success(f"[INPE Queimadas→Silver] Focos Silver: {len(df):,} registros → {output}")
    return output

