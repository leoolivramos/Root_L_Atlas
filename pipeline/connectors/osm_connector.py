"""
pipeline/connectors/osm_connector.py
======================================
Conector para extratos OpenStreetMap via Geofabrik.

Fonte: OpenStreetMap contributors / Geofabrik
Formato: PBF (Protocol Buffers Binary Format) — comprimido eficientemente
Licença: ODbL 1.0 — atribuição obrigatória
Escopo: Extrato "centro-oeste" do Geofabrik (cobre MT + GO + DF + MS)

ESTRATÉGIA:
    O extrato Centro-Oeste do Geofabrik (~300-500MB) é baixado completo
    e processado localmente com osmium/pyosmium para:
    1. Extração da rede viária para PostGIS (malha_viaria_osm)
    2. Preparação de arquivo OSM filtrado para futura importação no OSRM/Valhalla
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from connectors.base_connector import BaseConnector

_GEOFABRIK_URL = (
    "https://download.geofabrik.de/south-america/brazil/"
    "centro-oeste-latest.osm.pbf"
)

# Classes de vias a incluir na malha viária
_HIGHWAY_FILTER = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "unclassified", "residential", "service", "living_street",
    "motorway_link", "trunk_link", "primary_link",
    "secondary_link", "tertiary_link", "road",
}


class OSMConnector(BaseConnector):
    """
    Conector para OpenStreetMap via Geofabrik.

    Baixa o extrato PBF regional e utiliza osmium-tool para:
    - Filtrar apenas as vias relevantes
    - Recortar para a bounding box do Mato Grosso
    - Converter para GeoJSON para importação no PostGIS
    """

    SOURCE_ID = "osm_mt_pbf"

    # Bounding box aproximada do Mato Grosso (lon_min, lat_min, lon_max, lat_max)
    MT_BBOX = (-62.0, -20.0, -49.0, -7.0)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(source_id=self.SOURCE_ID, **kwargs)

    def get_download_url(self, **kwargs: Any) -> str:
        return _GEOFABRIK_URL

    def get_local_filename(self, url: str, **kwargs: Any) -> str:
        return "centro-oeste-latest.osm.pbf"

    def validate_raw_file(self, local_path: Path) -> bool:
        """Valida magic bytes do PBF (formato Protocol Buffers)."""
        if not local_path.exists():
            return False
        size = local_path.stat().st_size
        if size < 1_000_000:  # < 1 MB muito suspeito
            logger.warning(f"PBF suspeito (tamanho={size}): {local_path}")
            return False
        # PBF começa com header OSMHeader
        with open(local_path, "rb") as f:
            header = f.read(4)
        # Formato PBF: os primeiros bytes contêm comprimento do BlobHeader
        if len(header) < 4:
            return False
        return True

    def extract_mt_roads(
        self,
        pbf_path: Path,
        silver_path: Path,
    ) -> Path:
        """
        Extrai a rede viária do Mato Grosso do PBF usando osmium-tool.

        Requer osmium-tool instalado no sistema:
            apt-get install osmium-tool (Linux)
            brew install osmium-tool (macOS)

        Args:
            pbf_path: Caminho do PBF baixado (centro-oeste)
            silver_path: Destino do PBF recortado

        Returns:
            Path do PBF filtrado para MT
        """
        silver_path.mkdir(parents=True, exist_ok=True)

        # Passo 1: Recortar bounding box de MT
        mt_pbf = silver_path / "mt_roads.osm.pbf"
        bbox_str = ",".join(str(c) for c in self.MT_BBOX)

        if not mt_pbf.exists():
            logger.info(f"[OSM] Recortando bbox MT: {bbox_str}")
            cmd_bbox = [
                "osmium", "extract",
                "--bbox", bbox_str,
                "--output", str(mt_pbf),
                "--overwrite",
                str(pbf_path),
            ]
            self._run_osmium(cmd_bbox)

        # Passo 2: Filtrar apenas highways relevantes
        filtered_pbf = silver_path / "mt_highways.osm.pbf"
        if not filtered_pbf.exists():
            logger.info("[OSM] Filtrando vias relevantes...")
            highway_tags = " ".join(f"w/highway={h}" for h in _HIGHWAY_FILTER)
            cmd_filter = [
                "osmium", "tags-filter",
                str(mt_pbf),
                "w/highway",
                "--output", str(filtered_pbf),
                "--overwrite",
            ]
            self._run_osmium(cmd_filter)

        logger.success(f"[OSM] PBF de vias MT: {filtered_pbf}")
        return filtered_pbf

    def convert_to_geojson(
        self,
        pbf_path: Path,
        output_path: Path,
    ) -> Path:
        """Converte PBF para GeoJSON usando osmium export."""
        logger.info(f"[OSM] Convertendo {pbf_path.name} → GeoJSON...")
        cmd = [
            "osmium", "export",
            str(pbf_path),
            "--output", str(output_path),
            "--output-format", "geojson",
            "--overwrite",
            "--geometry-types", "linestring",  # Apenas linhas (vias)
        ]
        self._run_osmium(cmd)
        return output_path

    @staticmethod
    def _run_osmium(cmd: list[str]) -> None:
        """Executa osmium-tool como subprocesso."""
        logger.debug(f"Executando: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout:
                logger.debug(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"osmium falhou:\nstdout: {e.stdout}\nstderr: {e.stderr}")
            raise
        except FileNotFoundError:
            raise RuntimeError(
                "osmium-tool não encontrado. Instale com: apt-get install osmium-tool"
            )

    def import_to_postgis_via_ogr(
        self,
        geojson_path: Path,
        pg_connection: str,
    ) -> None:
        """
        Importa GeoJSON de vias para PostGIS usando ogr2ogr.

        Args:
            geojson_path: Path do GeoJSON exportado
            pg_connection: String de conexão PostgreSQL
        """
        logger.info("[OSM] Importando vias para PostGIS via ogr2ogr...")
        cmd = [
            "ogr2ogr",
            "-f", "PostgreSQL",
            f"PG:{pg_connection}",
            str(geojson_path),
            "-nln", "atlas.malha_viaria_osm_import",
            "-overwrite",
            "-t_srs", "EPSG:4326",
            "-lco", "GEOMETRY_NAME=geom",
            "-lco", "FID=osm_id",
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.success("[OSM] Importação concluída.")
        except subprocess.CalledProcessError as e:
            logger.error(f"ogr2ogr falhou: {e.stderr}")
            raise
