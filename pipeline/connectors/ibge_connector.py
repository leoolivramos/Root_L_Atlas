"""
pipeline/connectors/ibge_connector.py
=======================================
Conector para a Malha de Setores Censitários do IBGE.

Fonte: IBGE — Instituto Brasileiro de Geografia e Estatística
Dado: Malha de Setores Censitários do Censo 2022
Formato: GeoPackage / Shapefile (SIRGAS 2000, EPSG:4674)
Escopo: Estado de Mato Grosso (código UF: 51)
FTP base: https://geoftp.ibge.gov.br/organizacao_do_territorio/
"""

from __future__ import annotations

import ftplib
import zipfile
from pathlib import Path
from typing import Any

from loguru import logger

from connectors.base_connector import BaseConnector


# URLs canônicas dos dados censitários do IBGE (2022)
_IBGE_SETORES_URL = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
    "malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/"
    "censo_2022/setores/gpkg/UF/MT/MT_setores_CD2022.gpkg"
)

_IBGE_MUNICIPIOS_URL = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
    "malhas_territoriais/malhas_municipais/municipio_2022/"
    "Brasil/SHP/BR_Municipios_2022.zip"
)

# Código IBGE do Mato Grosso
_MT_UF_CODE = "51"


class IBGESetoresConnector(BaseConnector):
    """
    Conector para o download e preparação da malha de setores
    censitários do Censo 2022 do IBGE (Mato Grosso).
    """

    SOURCE_ID = "ibge_censo_2022_setores"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(source_id=self.SOURCE_ID, **kwargs)

    def get_download_url(self, **kwargs: Any) -> str:
        return _IBGE_SETORES_URL

    def get_local_filename(self, url: str, **kwargs: Any) -> str:
        return Path(url).name if url else "MT_setores_CD2022.gpkg"

    def validate_raw_file(self, local_path: Path) -> bool:
        """Valida se o arquivo baixado é um GeoPackage ou ZIP válido."""
        if not local_path.exists():
            return False
        if local_path.stat().st_size < 1_000_000:  # < 1 MB é suspeito
            logger.warning(f"Arquivo suspeito (muito pequeno): {local_path}")
            return False

        if local_path.suffix.lower() == ".gpkg":
            logger.info(f"Arquivo GeoPackage validado com sucesso: {local_path}")
            return True

        try:
            with zipfile.ZipFile(local_path) as zf:
                names = zf.namelist()
                has_gpkg = any(n.endswith(".gpkg") for n in names)
                has_shp = any(n.endswith(".shp") for n in names)
                if not (has_gpkg or has_shp):
                    logger.error(f"ZIP não contém .gpkg nem .shp: {names[:10]}")
                    return False
                logger.info(f"Estrutura do ZIP validada. Arquivos: {len(names)}")
                return True
        except zipfile.BadZipFile as e:
            logger.error(f"ZIP corrompido: {e}")
            return False

    def extract_to_silver(
        self,
        zip_path: Path,
        silver_path: Path,
        uf_code: str = _MT_UF_CODE,
    ) -> Path:
        """
        Extrai ou copia o GeoPackage/Shapefile para o diretório Silver.

        Args:
            zip_path: Caminho do arquivo GeoPackage ou ZIP baixado
            silver_path: Destino de extração
            uf_code: Código IBGE da UF (para log)

        Returns:
            Path do GeoPackage ou diretório do Shapefile extraído
        """
        silver_path.mkdir(parents=True, exist_ok=True)

        # Se já é um GeoPackage direto
        if zip_path.suffix.lower() == ".gpkg":
            dest = silver_path / zip_path.name
            if not dest.exists():
                import shutil
                shutil.copy2(zip_path, dest)
            return dest

        with zipfile.ZipFile(zip_path) as zf:
            # Prioriza GeoPackage (formato preferido)
            gpkg_files = [n for n in zf.namelist() if n.endswith(".gpkg")]
            shp_files = [n for n in zf.namelist() if n.endswith(".shp")]

            if gpkg_files:
                target_name = gpkg_files[0]
                logger.info(f"Extraindo GeoPackage: {target_name}")
                zf.extract(target_name, silver_path)
                return silver_path / target_name
            elif shp_files:
                # Extrai todos os componentes do Shapefile
                extensions = {".shp", ".dbf", ".shx", ".prj", ".cpg"}
                base = shp_files[0].replace(".shp", "")
                for member in zf.namelist():
                    if any(member.endswith(ext) for ext in extensions):
                        zf.extract(member, silver_path)
                return silver_path / shp_files[0]
            else:
                raise ValueError(f"Nenhum arquivo vetorial encontrado em {zip_path}")


class IBGEMunicipiosConnector(BaseConnector):
    """Conector para a malha de municípios do IBGE (2022)."""

    SOURCE_ID = "ibge_municipios_2022"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(source_id=self.SOURCE_ID, **kwargs)

    def get_download_url(self, **kwargs: Any) -> str:
        return _IBGE_MUNICIPIOS_URL

    def get_local_filename(self, url: str, **kwargs: Any) -> str:
        return "BR_Municipios_2022.zip"

    def validate_raw_file(self, local_path: Path) -> bool:
        if not local_path.exists():
            return False
        try:
            with zipfile.ZipFile(local_path) as zf:
                return any(n.endswith(".shp") for n in zf.namelist())
        except zipfile.BadZipFile:
            return False
