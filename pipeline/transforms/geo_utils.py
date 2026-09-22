"""
pipeline/transforms/geo_utils.py
==================================
Utilitários de processamento geoespacial do RootL Atlas.

Responsabilidades:
- Reprojeção de coordenadas (SIRGAS 2000 → WGS84)
- Validação topológica (geometrias inválidas → make_valid)
- Escrita GeoParquet com bbox_col nativo (índice espacial embutido)
- Cálculo de centróides
- Validação de limites territoriais (lat/lon dentro do MT)
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

try:
    from cep_to_coords.convert import cep_to_coords
    from cep_to_coords.strategies import CEPAbertoConverter
    CEP_TO_COORDS_AVAILABLE = True
except ImportError:
    CEP_TO_COORDS_AVAILABLE = False

import geopandas as gpd
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from loguru import logger
from shapely import make_valid
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.validation import explain_validity

# ─────────────────────────────────────────────────────────────────────────────
# Constantes de referência geodésica
# ─────────────────────────────────────────────────────────────────────────────

# SIRGAS 2000 — Sistema Geodésico de Referência adotado pelo IBGE
EPSG_SIRGAS2000 = 4674

# WGS84 — Sistema de referência global padrão (usado internamente)
EPSG_WGS84 = 4326

# Bounding box do estado de Mato Grosso (WGS84, com margem de tolerância)
MT_BBOX = {
    "lat_min": -20.5,
    "lat_max": -6.5,
    "lon_min": -62.0,
    "lon_max": -49.5,
}

# Bounding box do Brasil (para validações gerais)
BR_BBOX = {
    "lat_min": -34.0,
    "lat_max": 6.0,
    "lon_min": -74.0,
    "lon_max": -28.0,
}


# ─────────────────────────────────────────────────────────────────────────────
# Reprojeção
# ─────────────────────────────────────────────────────────────────────────────


def reproject_to_wgs84(
    gdf: gpd.GeoDataFrame,
    source_epsg: int = EPSG_SIRGAS2000,
) -> gpd.GeoDataFrame:
    """
    Reprojeta um GeoDataFrame para WGS84 (EPSG:4326).

    SIRGAS 2000 e WGS84 são praticamente coincidentes (~1m de diferença),
    mas a reprojeção explícita garante conformidade com os padrões da plataforma.

    Args:
        gdf: GeoDataFrame de entrada
        source_epsg: EPSG da projeção de origem

    Returns:
        GeoDataFrame reprojetado para EPSG:4326
    """
    if gdf.crs is None:
        logger.warning(
            f"GeoDataFrame sem CRS definido. Assumindo EPSG:{source_epsg}."
        )
        gdf = gdf.set_crs(epsg=source_epsg)

    current_epsg = gdf.crs.to_epsg()
    if current_epsg == EPSG_WGS84:
        logger.debug("CRS já é WGS84. Sem reprojeção necessária.")
        return gdf

    logger.info(
        f"Reprojetando EPSG:{current_epsg} → EPSG:{EPSG_WGS84}..."
    )
    return gdf.to_crs(epsg=EPSG_WGS84)


# ─────────────────────────────────────────────────────────────────────────────
# Validação topológica
# ─────────────────────────────────────────────────────────────────────────────


def validate_and_fix_geometries(
    gdf: gpd.GeoDataFrame,
    geometry_col: str = "geometry",
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """
    Valida todas as geometrias e corrige as inválidas com make_valid.

    Args:
        gdf: GeoDataFrame de entrada
        geometry_col: Nome da coluna de geometria

    Returns:
        Tupla (gdf_válido, relatório_de_problemas)
    """
    report_rows = []
    fixed_count = 0
    null_count = 0

    geometries = gdf[geometry_col].copy()

    for idx, geom in geometries.items():
        if geom is None or geom.is_empty:
            null_count += 1
            report_rows.append(
                {
                    "idx": idx,
                    "tipo": "geometria_nula_ou_vazia",
                    "descricao": "Geometry is None or empty",
                    "acao": "removido",
                }
            )
            continue

        if not geom.is_valid:
            reason = explain_validity(geom)
            fixed = make_valid(geom)
            gdf.at[idx, geometry_col] = fixed
            fixed_count += 1
            report_rows.append(
                {
                    "idx": idx,
                    "tipo": "geometria_invalida",
                    "descricao": reason,
                    "acao": "corrigido_com_make_valid",
                }
            )

    # Remove geometrias nulas/vazias
    gdf = gdf[gdf[geometry_col].notna() & ~gdf[geometry_col].is_empty].copy()

    report = pd.DataFrame(report_rows)

    logger.info(
        f"Validação geométrica: {fixed_count} corrigidas, "
        f"{null_count} removidas (nulas/vazias), "
        f"{len(gdf)} válidas."
    )

    if fixed_count > 0:
        logger.warning(
            f"{fixed_count} geometrias inválidas foram corrigidas com make_valid. "
            "Revise o relatório de problemas."
        )

    return gdf, report


# ─────────────────────────────────────────────────────────────────────────────
# Validação de limites territoriais
# ─────────────────────────────────────────────────────────────────────────────


def validate_coordinates_in_bbox(
    gdf: gpd.GeoDataFrame,
    bbox: dict[str, float] | None = None,
    strict: bool = False,
) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """
    Valida se as coordenadas dos centróides estão dentro de uma bbox.

    Para pontos, usa o próprio ponto. Para polígonos, usa o centróide.
    Elementos fora da bbox são isolados num relatório de violações.

    Args:
        gdf: GeoDataFrame de entrada (WGS84)
        bbox: Dicionário com lat_min, lat_max, lon_min, lon_max.
              Se None, usa os limites do Brasil.
        strict: Se True, levanta exceção quando há violações.

    Returns:
        Tupla (gdf_válido, relatório_violações)
    """
    if bbox is None:
        bbox = BR_BBOX

    centroids = gdf.geometry.centroid
    violacoes = []

    mask_valid = pd.Series(True, index=gdf.index)

    for idx, centroid in centroids.items():
        if centroid is None:
            continue
        lat, lon = centroid.y, centroid.x
        if not (bbox["lat_min"] <= lat <= bbox["lat_max"]):
            mask_valid[idx] = False
            violacoes.append(
                {
                    "idx": idx,
                    "lat": lat,
                    "lon": lon,
                    "violacao": f"lat={lat:.4f} fora de [{bbox['lat_min']}, {bbox['lat_max']}]",
                }
            )
        elif not (bbox["lon_min"] <= lon <= bbox["lon_max"]):
            mask_valid[idx] = False
            violacoes.append(
                {
                    "idx": idx,
                    "lat": lat,
                    "lon": lon,
                    "violacao": f"lon={lon:.4f} fora de [{bbox['lon_min']}, {bbox['lon_max']}]",
                }
            )

    report = pd.DataFrame(violacoes)

    if not report.empty:
        logger.error(
            f"VIOLAÇÃO TERRITORIAL: {len(report)} geometrias fora da bbox!\n"
            f"  Exemplos: {report['violacao'].head(3).tolist()}"
        )
        if strict:
            raise ValueError(
                f"Pipeline bloqueado: {len(report)} geometrias fora da bbox. "
                "Revise o relatório de violações."
            )

    return gdf[mask_valid], report


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo de centróides
# ─────────────────────────────────────────────────────────────────────────────


def add_centroid_column(
    gdf: gpd.GeoDataFrame,
    centroid_col: str = "centroide",
) -> gpd.GeoDataFrame:
    """
    Adiciona coluna de centróide geométrico ao GeoDataFrame.

    Para polígonos com geometria não convexa, o centróide pode cair
    fora do polígono — use point_on_surface nesses casos.

    Args:
        gdf: GeoDataFrame de entrada
        centroid_col: Nome da coluna de centróide

    Returns:
        GeoDataFrame com coluna adicional de centróide
    """
    gdf = gdf.copy()
    gdf[centroid_col] = gdf.geometry.centroid
    return gdf


def add_area_km2(
    gdf: gpd.GeoDataFrame,
    area_col: str = "area_km2",
    epsg_metric: int = 5880,  # SIRGAS 2000 / Brazil Polyconic
) -> gpd.GeoDataFrame:
    """
    Calcula área em km² usando uma projeção métrica adequada.

    IMPORTANTE: Nunca calcular área em WGS84 (graus). A reprojeção
    para uma projeção métrica é obrigatória para resultados precisos.

    Args:
        gdf: GeoDataFrame em WGS84
        area_col: Nome da coluna de área
        epsg_metric: EPSG da projeção métrica

    Returns:
        GeoDataFrame com coluna de área em km²
    """
    gdf = gdf.copy()
    gdf_metric = gdf.to_crs(epsg=epsg_metric)
    gdf[area_col] = (gdf_metric.geometry.area / 1_000_000).round(6)
    return gdf


# ─────────────────────────────────────────────────────────────────────────────
# Escrita GeoParquet com bbox_col nativo
# ─────────────────────────────────────────────────────────────────────────────


def write_geoparquet_with_bbox(
    gdf: gpd.GeoDataFrame,
    output_path: Path,
    geometry_col: str = "geometry",
    row_group_size: int = 50_000,
    compression: str = "snappy",
) -> Path:
    """
    Grava GeoDataFrame como GeoParquet com bbox_col nativo.

    A bbox_col é adicionada explicitamente nos metadados globais e
    por grupo de linhas. Isso cria um índice espacial embutido que
    permite a motores como DuckDB e Apache Arrow avaliar se um bloco
    de dados intersecta uma área de consulta SEM desserializar as
    geometrias completas — reduzindo latência de minutos para frações
    de segundo em conjuntos com dezenas de milhões de registros.

    Conformidade: GeoParquet spec 1.0
    (https://geoparquet.org/releases/v1.0.0/)

    Args:
        gdf: GeoDataFrame em EPSG:4326
        output_path: Caminho de saída do arquivo .parquet
        geometry_col: Nome da coluna de geometria
        row_group_size: Número de linhas por grupo (impacta índice espacial)
        compression: Codec de compressão (snappy, zstd, gzip)

    Returns:
        Path do arquivo criado
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if gdf.crs is None or gdf.crs.to_epsg() != EPSG_WGS84:
        raise ValueError(
            "GeoDataFrame deve estar em EPSG:4326 antes de gravar como GeoParquet."
        )

    logger.info(
        f"Gravando GeoParquet com bbox_col: {output_path} "
        f"({len(gdf):,} registros, compressão={compression})"
    )

    # geopandas >= 1.0 suporta bbox nativo via to_parquet
    gdf.to_parquet(
        output_path,
        geometry_encoding="WKB",
        write_covering_bbox=True,      # Habilita bbox_col por row group
        row_group_size=row_group_size,
        compression=compression,
        index=False,
        engine="pyarrow",
    )

    # Verifica o arquivo gerado
    pf = pq.read_metadata(output_path)
    logger.success(
        f"GeoParquet criado: {output_path.stat().st_size / 1024**2:.1f} MB | "
        f"{pf.num_rows:,} linhas | "
        f"{pf.num_row_groups} grupos de linhas"
    )

    return output_path


def read_geoparquet(
    path: Path,
    bbox: tuple[float, float, float, float] | None = None,
    columns: list[str] | None = None,
) -> gpd.GeoDataFrame:
    """
    Lê GeoParquet com filtragem espacial por bbox (pushdown via bbox_col).

    Args:
        path: Path do arquivo GeoParquet
        bbox: (lon_min, lat_min, lon_max, lat_max) — filtro espacial
        columns: Lista de colunas a ler (None = todas)

    Returns:
        GeoDataFrame filtrado
    """
    filters = None
    if bbox is not None:
        lon_min, lat_min, lon_max, lat_max = bbox
        # Filtros sobre a bbox_col para pushdown no leitor Parquet
        filters = [
            ("bbox.xmin", "<=", lon_max),
            ("bbox.xmax", ">=", lon_min),
            ("bbox.ymin", "<=", lat_max),
            ("bbox.ymax", ">=", lat_min),
        ]

    return gpd.read_parquet(
        path,
        columns=columns,
        filters=filters,
        engine="pyarrow",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Geocodificador exclusivo via pacote cep-to-coords (ViaCEP + Photon OSM)
# ─────────────────────────────────────────────────────────────────────────────


class CEPToCoordsGeocoder:
    """
    Geocodificador de CEPs brasileiros utilizando exclusivamente o pacote `cep-to-coords`.
    Estratégias suportadas:
    1. CorreiosPhotonConverter (ViaCEP + Photon OSM) - Padrão
    2. CEPAbertoConverter (se variável CEP_ABERTO_TOKEN estiver configurada)

    Recursos:
    - Normalização e validação de CEPs (8 dígitos).
    - Cache persistente em arquivo JSON para evitar requisições redundantes.
    - Validação de pertinência territorial (prioriza MT e valida Brasil).
    - Migração transparente de cache pré-existente.
    """

    def __init__(
        self,
        cache_path: Path | str | None = None,
        delay_seconds: float = 0.05,
    ) -> None:
        self.cache_path = Path(cache_path) if cache_path else None
        self.delay_seconds = delay_seconds
        self._cache: dict[str, dict[str, Any]] = {}
        self._dirty = False
        self._lock = threading.RLock()
        self._load_cache()

    def _load_cache(self) -> None:
        with self._lock:
            if self.cache_path and self.cache_path.exists():
                try:
                    with open(self.cache_path, "r", encoding="utf-8") as f:
                        self._cache = json.load(f)
                    logger.info(f"[CEPToCoordsGeocoder] Cache carregado: {len(self._cache):,} CEPs em {self.cache_path}")
                    return
                except Exception as e:
                    logger.warning(f"[CEPToCoordsGeocoder] Erro ao carregar cache de {self.cache_path}: {e}")
                    self._cache = {}

            # Migração transparente se existir cache anterior (ex: nominatim_cep_cache.json)
            if self.cache_path:
                legacy_path = self.cache_path.parent / "nominatim_cep_cache.json"
                if legacy_path.exists():
                    try:
                        with open(legacy_path, "r", encoding="utf-8") as f:
                            legacy_cache = json.load(f)
                        migrated = 0
                        for k, v in legacy_cache.items():
                            if isinstance(v, dict) and v.get("found") and v.get("lat") and v.get("lon"):
                                self._cache[k] = {
                                    "found": True,
                                    "cep": k,
                                    "lat": float(v["lat"]),
                                    "lon": float(v["lon"]),
                                    "source": "migrated_cache",
                                }
                                migrated += 1
                        if migrated > 0:
                            self._dirty = True
                            logger.info(f"[CEPToCoordsGeocoder] {migrated:,} CEPs válidos migrados do cache anterior.")
                            self.save_cache()
                    except Exception as e:
                        logger.debug(f"[CEPToCoordsGeocoder] Falha na migração do cache legado: {e}")

    def save_cache(self) -> None:
        with self._lock:
            if not (self.cache_path and self._dirty):
                return
            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self.cache_path.with_suffix(".tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f, ensure_ascii=False, indent=2)
                tmp_path.replace(self.cache_path)
                self._dirty = False
                logger.debug(f"[CEPToCoordsGeocoder] Cache salvo: {len(self._cache):,} CEPs em {self.cache_path}")
            except Exception as e:
                logger.error(f"[CEPToCoordsGeocoder] Falha ao salvar cache: {e}")

    @staticmethod
    def clean_cep(cep: Any) -> str | None:
        """Sanitiza e valida um CEP brasileiro de 8 dígitos."""
        if cep is None or pd.isna(cep):
            return None
        s = str(cep).strip()
        if s.endswith(".0"):
            s = s[:-2]
        digits = re.sub(r"\D", "", s)
        if not digits:
            return None
        digits = digits.zfill(8)
        if len(digits) != 8:
            return None
        if digits in ("00000000", "99999999"):
            return None
        return digits

    def geocode_cep(self, raw_cep: Any) -> dict[str, Any] | None:
        """
        Geocodifica um único CEP utilizando exclusivamente o pacote cep-to-coords.
        Retorna dict com lat, lon, geometry ou None se não encontrado.
        """
        cep = self.clean_cep(raw_cep)
        if not cep:
            return None

        with self._lock:
            if cep in self._cache:
                entry = self._cache[cep]
                if entry.get("found"):
                    return entry
                return None

        if not CEP_TO_COORDS_AVAILABLE:
            logger.error("[CEPToCoordsGeocoder] Pacote cep-to-coords não está instalado no ambiente!")
            return None

        fmt_cep = f"{cep[:5]}-{cep[5:]}"

        # Estratégia 1: cep-to-coords padrão (ViaCEP + Photon OSM)
        try:
            coords = cep_to_coords(fmt_cep)
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if lat is not None and lon is not None and not math.isnan(lat) and not math.isnan(lon):
                lat = float(lat)
                lon = float(lon)
                is_brazil = (
                    BR_BBOX["lat_min"] <= lat <= BR_BBOX["lat_max"]
                    and BR_BBOX["lon_min"] <= lon <= BR_BBOX["lon_max"]
                )
                if is_brazil:
                    entry = {
                        "found": True,
                        "cep": cep,
                        "lat": lat,
                        "lon": lon,
                        "source": "cep_to_coords",
                    }
                    with self._lock:
                        self._cache[cep] = entry
                        self._dirty = True
                    return entry
        except Exception as e:
            logger.debug(f"[CEPToCoordsGeocoder] Erro cep-to-coords em {fmt_cep}: {e}")

        # Estratégia 2: CEPAberto (se token configurado)
        if os.getenv("CEP_ABERTO_TOKEN"):
            try:
                coords = cep_to_coords(fmt_cep, factory=CEPAbertoConverter)
                lat = coords.get("latitude")
                lon = coords.get("longitude")
                if lat is not None and lon is not None and not math.isnan(lat) and not math.isnan(lon):
                    lat = float(lat)
                    lon = float(lon)
                    is_brazil = (
                        BR_BBOX["lat_min"] <= lat <= BR_BBOX["lat_max"]
                        and BR_BBOX["lon_min"] <= lon <= BR_BBOX["lon_max"]
                    )
                    if is_brazil:
                        entry = {
                            "found": True,
                            "cep": cep,
                            "lat": lat,
                            "lon": lon,
                            "source": "cep_aberto",
                        }
                        with self._lock:
                            self._cache[cep] = entry
                            self._dirty = True
                        return entry
            except Exception as e:
                logger.debug(f"[CEPToCoordsGeocoder] Erro CEPAberto em {fmt_cep}: {e}")

        # Registra no cache que não foi encontrado para não repetir tentativas
        with self._lock:
            self._cache[cep] = {"found": False, "cep": cep}
            self._dirty = True
        return None

    def batch_geocode(
        self,
        ceps: list[Any],
        max_workers: int = 6,
        save_every: int = 25,
        delay_seconds: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Geocodifica uma lista de CEPs em lote com suporte a concorrência e persistência incremental de cache.
        Retorna dicionário {cep_limpo: resultado_valido}.
        """
        delay = delay_seconds if delay_seconds is not None else self.delay_seconds
        clean_ceps = {c for raw in ceps if (c := self.clean_cep(raw)) is not None}

        with self._lock:
            cached_found = sum(1 for c in clean_ceps if c in self._cache and self._cache[c].get("found"))
            cached_not_found = sum(1 for c in clean_ceps if c in self._cache and not self._cache[c].get("found"))
            pending = [c for c in clean_ceps if c not in self._cache]

        logger.info(
            f"[CEPToCoordsGeocoder] Total únicos: {len(clean_ceps):,} | "
            f"No cache: {cached_found} encontrados, {cached_not_found} não encontrados | "
            f"Pendentes de consulta via cep-to-coords: {len(pending):,}"
        )

        if pending:
            if max_workers > 1 and len(pending) > 1:
                query_count = 0
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(self.geocode_cep, cep): cep for cep in pending}
                    for i, future in enumerate(as_completed(futures), 1):
                        try:
                            future.result()
                        except Exception as e:
                            logger.debug(f"[CEPToCoordsGeocoder] Erro em worker concorrente: {e}")
                        query_count += 1
                        if query_count % save_every == 0:
                            self.save_cache()
                            logger.info(f"  [CEPToCoordsGeocoder] Progresso: {i:,}/{len(pending):,} consultas concluídas...")
            else:
                query_count = 0
                for i, cep in enumerate(pending, 1):
                    self.geocode_cep(cep)
                    query_count += 1
                    if delay > 0:
                        time.sleep(delay)
                    if query_count % save_every == 0:
                        self.save_cache()
                        logger.info(f"  [CEPToCoordsGeocoder] Progresso: {i:,}/{len(pending):,} consultas realizadas...")

            self.save_cache()

        results = {}
        with self._lock:
            for c in clean_ceps:
                entry = self._cache.get(c)
                if entry and entry.get("found"):
                    results[c] = entry
        return results


# Alias de compatibilidade retroativa para código legado
NominatimCEPGeocoder = CEPToCoordsGeocoder

