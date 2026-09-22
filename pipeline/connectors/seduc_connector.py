"""
pipeline/connectors/seduc_connector.py
======================================
Conector para o Cadastro de Escolas da SEDUC-MT (2021).

Fonte: Secretaria de Estado de Educação de Mato Grosso (SEDUC-MT)
Dado: Cadastro de Escolas 2021
Formato: XLSX
Finalidade: Cruzamento e refinamento cadastral e espacial de escolas em MT
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
import urllib.request

import pandas as pd
from loguru import logger

from connectors.base_connector import BaseConnector, IngestionManifest

_SEDUC_URL = (
    "https://www3.seduc.mt.gov.br/documents/8125245/22260828/"
    "CADASTRO+DE+ESCOLA+2021.xlsx/21d101a9-8745-d3a7-9da8-6a188f81984c"
)


class SEDUCEscolasConnector(BaseConnector):
    """
    Conector para download e extração do Cadastro de Escolas SEDUC-MT 2021.
    """

    SOURCE_ID = "seduc_escolas_2021"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(source_id=self.SOURCE_ID, **kwargs)

    def get_download_url(self, **kwargs: Any) -> str:
        return _SEDUC_URL

    def get_local_filename(self, url: str, **kwargs: Any) -> str:
        return "cadastro_escolas_2021.xlsx"

    def validate_raw_file(self, local_path: Path) -> bool:
        return local_path.exists() and local_path.stat().st_size > 50_000

    def download(self, target_path: Path | None = None) -> Path:
        """Faz o download com User-Agent apropriado se não existir localmente."""
        self.bronze_path.mkdir(parents=True, exist_ok=True)
        dest = target_path or (self.bronze_path / self.get_local_filename(""))

        # Verifica se já existe em paths conhecidos (ex: pipeline/data/seduc/)
        bundled_copy = Path(__file__).resolve().parent.parent / "data" / "seduc" / "cadastro_escolas_2021.xlsx"
        if not dest.exists() and bundled_copy.exists():
            import shutil
            shutil.copy2(bundled_copy, dest)
            logger.info(f"[{self.source_id}] Copiado arquivo embutido: {bundled_copy} → {dest}")
            return dest

        if not dest.exists():
            logger.info(f"[{self.source_id}] Baixando {self.get_download_url()}...")
            req = urllib.request.Request(
                self.get_download_url(),
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RootLAtlas/1.0"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read()
                dest.write_bytes(content)
            logger.success(f"[{self.source_id}] Download concluído: {dest} ({len(content):,} bytes)")

        return dest

    @staticmethod
    def load_seduc_df(xlsx_path: Path) -> pd.DataFrame:
        """
        Lê a planilha da SEDUC-MT formatando colunas padronizadas.
        Retorna DataFrame com chave 'co_entidade', 'seduc_cep', 'seduc_logradouro',
        'seduc_numero', 'seduc_bairro', 'seduc_municipio', 'seduc_nome_escola'.
        """
        logger.info(f"Lendo cadastro de escolas SEDUC-MT: {xlsx_path}...")
        df = pd.read_excel(xlsx_path, skiprows=11)

        # Mapeia colunas esperadas
        col_map = {
            "Cód. Escola": "co_entidade",
            "Nome da Escola": "seduc_nome_escola",
            "Município": "seduc_municipio",
            "Logradouro": "seduc_logradouro",
            "Número": "seduc_numero",
            "Bairro": "seduc_bairro",
            "CEP": "seduc_cep",
            "Localização": "seduc_localizacao",
            "Dep. Adm.": "seduc_dep_adm",
            "Sit. Func.": "seduc_sit_func",
        }
        existing = {k: v for k, v in col_map.items() if k in df.columns}
        df = df.rename(columns=existing)

        # Filtra registros com código de escola válido
        df["co_entidade"] = pd.to_numeric(df["co_entidade"], errors="coerce")
        df = df.dropna(subset=["co_entidade"]).copy()
        df["co_entidade"] = df["co_entidade"].astype(int)

        # Sanitiza CEP
        if "seduc_cep" in df.columns:
            df["seduc_cep"] = (
                df["seduc_cep"]
                .astype(str)
                .str.replace(r"\.0$", "", regex=True)
                .str.replace(r"\D", "", regex=True)
                .str.strip()
                .str.zfill(8)
            )

        logger.info(f"  {len(df):,} escolas válidas carregadas da SEDUC-MT")
        return df
