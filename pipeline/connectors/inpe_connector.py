"""
pipeline/connectors/inpe_connector.py
======================================
Conector para os dados de Focos de Calor e Queimadas — INPE (BDQueimadas).

Fonte: INPE — Instituto Nacional de Pesquisas Espaciais (Programa Queimadas)
URL: https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/
Formato: CSV e ZIP mensais (focos_mensal_br_YYYYMM.csv / focos_mensal_br_YYYYMM.zip)
Escopo: Filtro on-the-fly para Mato Grosso (estado_id == '51' ou estado == 'MATO GROSSO')
"""

from __future__ import annotations

import csv
import io
import re
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

from connectors.base_connector import BaseConnector, IngestionManifest

_INPE_BASE_URL = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/"
_MT_ESTADO_ID = "51"
_MT_ESTADO_NOME = "MATO GROSSO"


class INPEQueimadasConnector(BaseConnector):
    """
    Conector para download e extração dos focos de calor mensais do INPE para Mato Grosso.
    """

    SOURCE_ID = "inpe_bdqueimadas_mensal"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(source_id=self.SOURCE_ID, **kwargs)
        self.base_url = _INPE_BASE_URL

    def get_download_url(self, filename: str = "", **kwargs: Any) -> str:
        if filename:
            return f"{self.base_url.rstrip('/')}/{filename}"
        return self.base_url

    def get_local_filename(self, url: str, **kwargs: Any) -> str:
        year_month = kwargs.get("year_month", "")
        if year_month:
            return f"focos_queimadas_mt_{year_month}.csv"
        return Path(url).name

    def validate_raw_file(self, local_path: Path) -> bool:
        return local_path.exists() and local_path.stat().st_size > 50

    def list_available_files(self) -> list[str]:
        """Consulta o servidor HTTP do INPE e descobre os arquivos mensais disponíveis."""
        try:
            req = urllib.request.Request(self.base_url, headers={"User-Agent": "Mozilla/5.0 (RootL Atlas)"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
                files = re.findall(r'href=[\'"]([^\'"]+\.(?:csv|zip))[\'"]', html)
                valid_files = [f for f in files if re.match(r"^focos_mensal_br_\d{6}\.(csv|zip)$", f)]
                valid_files.sort()
                logger.info(f"[{self.source_id}] {len(valid_files)} arquivos mensais encontrados no INPE.")
                return valid_files
        except Exception as exc:
            logger.error(f"[{self.source_id}] Falha ao listar arquivos do INPE: {exc}")
            return []

    def download_and_filter_month(self, filename: str) -> tuple[Path, IngestionManifest] | None:
        """
        Baixa um arquivo mensal do Brasil (.csv ou .zip), filtra on-the-fly
        as detecções de Mato Grosso (UF=51) e grava o CSV filtrado no Bronze.
        """
        m = re.match(r"^focos_mensal_br_(\d{6})\.(csv|zip)$", filename)
        if not m:
            logger.warning(f"[{self.source_id}] Nome de arquivo inválido: {filename}")
            return None

        year_month = m.group(1)
        ext = m.group(2).lower()
        self.bronze_path.mkdir(parents=True, exist_ok=True)
        local_target = self.bronze_path / f"focos_queimadas_mt_{year_month}.csv"

        if local_target.exists() and local_target.stat().st_size > 100:
            logger.info(f"[{self.source_id}] Arquivo já existe no Bronze: {local_target}. Reutilizando...")
            manifest = self._create_manifest(local_target, self.get_download_url(filename))
            return local_target, manifest

        url = self.get_download_url(filename)
        logger.info(f"[{self.source_id}] Baixando e filtrando MT para {year_month} de {url}...")

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (RootL Atlas)"})

        matched_rows: list[dict[str, Any]] = []
        fieldnames: list[str] = []

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                if ext == "zip":
                    zip_bytes = resp.read()
                    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                        csv_name = [n for n in zf.namelist() if n.endswith(".csv")][0]
                        with zf.open(csv_name) as csv_file:
                            reader = csv.DictReader(io.TextIOWrapper(csv_file, encoding="utf-8", errors="ignore"))
                            fieldnames = list(reader.fieldnames or [])
                            for row in reader:
                                if str(row.get("estado_id", "")).strip() == _MT_ESTADO_ID or \
                                   str(row.get("estado", "")).strip().upper() == _MT_ESTADO_NOME:
                                    matched_rows.append(row)
                else:
                    # CSV stream direto
                    text_stream = io.TextIOWrapper(resp, encoding="utf-8", errors="ignore")
                    reader = csv.DictReader(text_stream)
                    fieldnames = list(reader.fieldnames or [])
                    for row in reader:
                        if str(row.get("estado_id", "")).strip() == _MT_ESTADO_ID or \
                           str(row.get("estado", "")).strip().upper() == _MT_ESTADO_NOME:
                            matched_rows.append(row)

            # Grava no Bronze local
            if not fieldnames and matched_rows:
                fieldnames = list(matched_rows[0].keys())

            with open(local_target, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(matched_rows)

            logger.info(
                f"[{self.source_id}] Mês {year_month} processado com sucesso: "
                f"{len(matched_rows):,} focos em MT gravados em {local_target}"
            )

            manifest = self._create_manifest(local_target, url)
            manifest.record_count = len(matched_rows)
            manifest.save(self.manifest_dir)

            return local_target, manifest

        except Exception as exc:
            logger.error(f"[{self.source_id}] Erro ao processar mês {year_month}: {exc}")
            return None

    def ingest(self, months: list[str] | None = None, **kwargs: Any) -> list[tuple[Path, IngestionManifest]]:
        """
        Executa a ingestão para os meses solicitados (formato YYYYMM) ou para os meses mais recentes.
        """
        available = self.list_available_files()
        if not available:
            logger.warning(f"[{self.source_id}] Nenhum arquivo disponível no INPE.")
            return []

        # Se months não foi passado, seleciona os meses de 2024 e 2025 disponíveis
        target_files: list[str] = []
        if months:
            for m in months:
                matching = [f for f in available if f"_{m}." in f]
                target_files.extend(matching)
        else:
            # Padrão: meses de 2024 e 2025
            target_files = [f for f in available if any(f"_{y}" in f for y in ["2024", "2025"])]
            # Se não houver, pega os últimos 6 arquivos disponíveis
            if not target_files:
                target_files = available[-6:]

        results: list[tuple[Path, IngestionManifest]] = []
        for fn in target_files:
            res = self.download_and_filter_month(fn)
            if res:
                results.append(res)

        return results
