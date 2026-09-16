"""
pipeline/connectors/inep_connector.py
=======================================
Conector para os Microdados do Censo Escolar — INEP.

Fonte: INEP — Instituto Nacional de Estudos e Pesquisas Educacionais
Dado: Microdados do Censo Escolar (escolas, matrículas, turmas)
Formato: CSV (separador "|") dentro de ZIP
Codificação: latin-1 (ISO-8859-1)
Georreferenciamento: colunas NU_LATITUDE, NU_LONGITUDE
Escopo: Filtro por CO_UF = 51 (Mato Grosso)
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any

from loguru import logger

from connectors.base_connector import BaseConnector

# URL base para microdados do Censo Escolar
# INEP publica no padrão: microdados_censo_escolar_{year}.zip
_INEP_BASE_URL = (
    "https://download.inep.gov.br/dados_abertos/"
    "microdados_censo_escolar_{year}.zip"
)

# Código IBGE do Mato Grosso
_MT_CO_UF = "51"


class INEPCensoEscolarConnector(BaseConnector):
    """
    Conector para download e extração dos Microdados do Censo Escolar.

    O arquivo contém CSV com separador "|" e encoding latin-1.
    A tabela principal de escolas (ESCOLA.CSV ou ESCOLAS.CSV) contém
    coordenadas em NU_LATITUDE e NU_LONGITUDE.
    """

    SOURCE_ID = "inep_censo_escolar_2025"

    def __init__(self, year: int = 2024, **kwargs: Any) -> None:
        super().__init__(source_id=self.SOURCE_ID, **kwargs)
        self.year = year

    def get_download_url(self, **kwargs: Any) -> str:
        year = kwargs.get("year", self.year)
        return _INEP_BASE_URL.format(year=year)

    def get_local_filename(self, url: str, **kwargs: Any) -> str:
        year = kwargs.get("year", self.year)
        return f"microdados_censo_escolar_{year}.zip"

    def validate_raw_file(self, local_path: Path) -> bool:
        """Valida presença do CSV de escolas no ZIP."""
        if not local_path.exists():
            return False
        if local_path.stat().st_size < 5_000_000:  # < 5 MB
            logger.warning(f"ZIP INEP suspeito (pequeno demais): {local_path}")
            return False
        try:
            with zipfile.ZipFile(local_path) as zf:
                names = [n.upper() for n in zf.namelist()]
                has_escola = any("ESCOLA" in n and n.endswith(".CSV") for n in names)
                if not has_escola:
                    logger.error(f"CSV de escolas não encontrado. Conteúdo: {names[:10]}")
                    return False
                return True
        except zipfile.BadZipFile as e:
            logger.error(f"ZIP INEP corrompido: {e}")
            return False

    def find_escola_csv(self, zip_path: Path) -> str | None:
        """
        Localiza o arquivo CSV de escolas dentro do ZIP.
        O INEP muda o nome entre edições (ESCOLA.CSV, ESCOLAS.CSV, etc.).
        """
        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                upper = name.upper()
                if "ESCOLA" in upper and upper.endswith(".CSV"):
                    logger.info(f"CSV de escolas identificado: {name}")
                    return name
        return None

    def extract_escola_csv(
        self,
        zip_path: Path,
        silver_path: Path,
        uf_filter: str = _MT_CO_UF,
    ) -> Path:
        """
        Extrai o CSV de escolas do ZIP para o diretório Silver.
        Realiza pré-filtragem por UF durante a leitura (economia de memória).

        Args:
            zip_path: Caminho do ZIP baixado
            silver_path: Diretório de destino
            uf_filter: Código de UF para filtro (51 = MT)

        Returns:
            Path do CSV extraído (já filtrado por MT)
        """
        import io

        import pandas as pd

        csv_name = self.find_escola_csv(zip_path)
        if not csv_name:
            raise ValueError(f"CSV de escolas não encontrado em {zip_path}")

        silver_path.mkdir(parents=True, exist_ok=True)
        output_path = silver_path / f"escolas_mt_{self.year}.csv"

        logger.info(f"Extraindo e filtrando escolas de MT (CO_UF={uf_filter})...")

        with zipfile.ZipFile(zip_path) as zf:
            # Detecta delimitador a partir da primeira linha
            with zf.open(csv_name) as raw_peek:
                first_line = raw_peek.readline().decode("latin-1", errors="ignore")
                sep = ";" if ";" in first_line else ("|" if "|" in first_line else ",")
                logger.info(f"Delimitador detectado para {csv_name}: {sep!r}")

            with zf.open(csv_name) as raw:
                # Leitura em chunks para economizar memória
                chunks = []
                for chunk in pd.read_csv(
                    io.TextIOWrapper(raw, encoding="latin-1"),
                    sep=sep,
                    chunksize=100_000,
                    low_memory=False,
                    dtype={"CO_UF": str, "CO_MUNICIPIO": str, "SG_UF": str},
                ):
                    if "CO_UF" in chunk.columns:
                        mt_chunk = chunk[chunk["CO_UF"].astype(str) == str(uf_filter)]
                    elif "SG_UF" in chunk.columns:
                        mt_chunk = chunk[chunk["SG_UF"].astype(str).str.upper() == "MT"]
                    else:
                        mt_chunk = chunk
                    if not mt_chunk.empty:
                        chunks.append(mt_chunk)

        if not chunks:
            raise ValueError(f"Nenhuma escola encontrada para CO_UF={uf_filter}")

        df = pd.concat(chunks, ignore_index=True)
        df.to_csv(output_path, index=False, encoding="utf-8")

        logger.success(
            f"Escolas MT extraídas: {len(df):,} registros → {output_path}"
        )
        return output_path
