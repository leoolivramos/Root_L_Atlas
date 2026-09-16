"""
pipeline/connectors/datasus_connector.py
==========================================
Conector para o Cadastro Nacional de Estabelecimentos de Saúde (CNES).

Fonte: DATASUS / Ministério da Saúde
Formato: DBC (dBASE comprimido) / Parquet via pysus
Biblioteca obrigatória: pysus
Escopo: Estado de Mato Grosso (ST = STMT{AAMM}.dbc)
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from connectors.base_connector import BaseConnector, IngestionManifest

_MT_STATE_CODE = "MT"


class DATASUSCNESConnector(BaseConnector):
    """
    Conector para o CNES/DATASUS utilizando pysus.
    """

    SOURCE_ID = "datasus_cnes_estab"

    def __init__(
        self,
        competencia: date | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(source_id=self.SOURCE_ID, **kwargs)
        if competencia is None:
            self.competencia = date(2024, 1, 1)  # Competência estável padrão 2024
        else:
            self.competencia = competencia

    def get_download_url(self, **kwargs: Any) -> str:
        comp = kwargs.get("competencia", self.competencia)
        aamm = comp.strftime("%y%m")
        return f"ftp://ftp.datasus.gov.br/dissemin/publicos/CNES/200508_/Dados/ST/ST{_MT_STATE_CODE}{aamm}.dbc"

    def get_local_filename(self, url: str, **kwargs: Any) -> str:
        comp = kwargs.get("competencia", self.competencia)
        aamm = comp.strftime("%y%m")
        return f"cnes_mt_{aamm}.parquet"

    def validate_raw_file(self, local_path: Path) -> bool:
        return local_path.exists() and local_path.stat().st_size > 10_000

    def ingest(self, **kwargs: Any) -> tuple[Path, IngestionManifest]:
        """
        Ingestão CNES via PySUS, gravando diretamente Parquet padronizado no Bronze.
        """
        self.bronze_path.mkdir(parents=True, exist_ok=True)
        local_path = self.bronze_path / self.get_local_filename("")

        if not local_path.exists():
            logger.info(f"[{self.source_id}] Baixando CNES/MT via PySUS ({self.competencia.year}/{self.competencia.month:02d})...")
            import pysus
            if hasattr(pysus, "cnes"):
                df = pysus.cnes(_MT_STATE_CODE, self.competencia.year, self.competencia.month, group="ST", as_dataframe=True)
            elif hasattr(pysus, "ftp") and hasattr(pysus.ftp, "cnes"):
                df = pysus.ftp.cnes(_MT_STATE_CODE, self.competencia.year, self.competencia.month, group="ST", as_dataframe=True)
            else:
                from pysus.online_data.CNES import download
                df = download(state=_MT_STATE_CODE, year=self.competencia.year, month=self.competencia.month, group="ST")

            if df is None or df.empty:
                raise ValueError(f"PySUS retornou vazio para CNES/MT {self.competencia.year}/{self.competencia.month:02d}")

            logger.info(f"[{self.source_id}] {len(df):,} estabelecimentos obtidos")
            df.to_parquet(local_path, index=False, engine="pyarrow", compression="snappy")
            logger.success(f"[{self.source_id}] Parquet gerado no Bronze: {local_path}")

        file_hash = self.compute_sha256(local_path)
        manifest = IngestionManifest(
            source_id=self.source_id,
            url=self.get_download_url(),
            local_path=local_path,
            file_hash=file_hash,
            extracted_at=datetime.now(timezone.utc),
            file_size_bytes=local_path.stat().st_size,
            record_count=len(df) if "df" in locals() else None,
        )
        self._upload_to_minio(local_path, f"{self.source_id}/{local_path.name}")
        manifest.save(self.manifest_dir)
        return local_path, manifest
