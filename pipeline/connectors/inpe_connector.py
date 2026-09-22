"""
pipeline/connectors/inpe_connector.py
======================================
Conector para os dados de Focos de Calor e Queimadas — INPE (BDQueimadas).

Fontes:
  1. Mensais — Brasil inteiro, todos satélites (2023–hoje):
     https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/
     Formato: focos_mensal_br_YYYYMM.{csv|zip}

  2. Anuais — Brasil inteiro, todos satélites (1998–2025):
     https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_todos_sats/
     Formato: focos_br_todos-sats_YYYY.zip

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

# ─── URLs base ────────────────────────────────────────────────────────────────

# Mensais: Brasil inteiro, todos satélites (2023 em diante)
_INPE_BASE_URL = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/mensal/Brasil/"

# Anuais: Brasil inteiro, TODOS os satélites (1998–2025)
_INPE_ANUAL_TODOS_SATS_URL = (
    "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_todos_sats/"
)

_MT_ESTADO_ID = "51"
_MT_ESTADO_NOME = "MATO GROSSO"


# ─── Funções auxiliares ───────────────────────────────────────────────────────

def _is_mt_row(row: dict[str, Any]) -> bool:
    """Verifica se um registro de foco pertence ao Mato Grosso (UF 51)."""
    return (
        str(row.get("estado_id", "")).strip() == _MT_ESTADO_ID
        or str(row.get("estado", "")).strip().upper() == _MT_ESTADO_NOME
    )


def _stream_zip_filter_mt(
    zip_bytes: bytes,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Extrai o primeiro CSV de um ZIP em memória e filtra apenas registros de MT."""
    matched_rows: list[dict[str, Any]] = []
    fieldnames: list[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        csv_name = next((n for n in zf.namelist() if n.endswith(".csv")), None)
        if not csv_name:
            raise ValueError("Nenhum arquivo CSV encontrado dentro do ZIP.")
        with zf.open(csv_name) as csv_file:
            reader = csv.DictReader(
                io.TextIOWrapper(csv_file, encoding="utf-8", errors="ignore")
            )
            fieldnames = list(reader.fieldnames or [])
            for row in reader:
                if _is_mt_row(row):
                    matched_rows.append(row)
    return fieldnames, matched_rows


def _write_bronze_csv(
    local_target: Path,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> None:
    """Grava registros filtrados no Bronze como CSV UTF-8."""
    if not fieldnames and rows:
        fieldnames = list(rows[0].keys())
    with open(local_target, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ─── Conector ─────────────────────────────────────────────────────────────────

class INPEQueimadasConnector(BaseConnector):
    """
    Conector para download e extração dos focos de calor do INPE para Mato Grosso.

    Suporta duas granularidades:
    - Anual (todos satélites): `ingest_annual_todos_sats(years=[2020, ..., 2025])`
    - Mensal (todos satélites): `ingest(year_from=2026)` ou `ingest(months=["202601", ...])`
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

    # ─── Ingestão Anual (todos satélites, 1998–2025) ─────────────────────────

    def ingest_annual_todos_sats(
        self,
        years: list[int],
    ) -> list[tuple[Path, IngestionManifest]]:
        """
        Baixa os arquivos anuais (TODOS os satélites) do INPE para os anos solicitados,
        filtra on-the-fly para Mato Grosso e salva um CSV por ano no Bronze.

        Fonte: focos/csv/anual/Brasil_todos_sats/focos_br_todos-sats_YYYY.zip
        Cobertura disponível no servidor: 1998–2025.
        Uso recomendado: anos completos (2020–2025) antes de completar com mensais de 2026+.

        Args:
            years: Lista de anos inteiros (ex: [2020, 2021, 2022, 2023, 2024, 2025]).

        Returns:
            Lista de tuplas (Path do CSV Bronze, IngestionManifest).
        """
        self.bronze_path.mkdir(parents=True, exist_ok=True)
        results: list[tuple[Path, IngestionManifest]] = []

        for year in sorted(years):
            filename = f"focos_br_todos-sats_{year}.zip"
            url = f"{_INPE_ANUAL_TODOS_SATS_URL}{filename}"
            # Padrão de nomenclatura Bronze: focos_queimadas_mt_YYYY.csv
            local_target = self.bronze_path / f"focos_queimadas_mt_{year}.csv"

            # Cache: reutiliza arquivo Bronze já existente
            if local_target.exists() and local_target.stat().st_size > 100:
                logger.info(
                    f"[{self.source_id}] Ano {year}: já no Bronze "
                    f"({local_target.stat().st_size / 1024:.0f} KB). Reutilizando."
                )
                manifest = self._create_manifest(local_target, url)
                results.append((local_target, manifest))
                continue

            logger.info(
                f"[{self.source_id}] Baixando ano {year} (todos satélites, Brasil) → {url}"
            )
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (RootL Atlas)"}
            )

            try:
                # Timeout generoso: ZIPs anuais podem ter 8–30 MB
                with urllib.request.urlopen(req, timeout=300) as resp:
                    zip_bytes = resp.read()

                size_mb = len(zip_bytes) / 1024 / 1024
                logger.info(
                    f"[{self.source_id}] Ano {year}: {size_mb:.1f} MB baixados. "
                    "Filtrando MT on-the-fly..."
                )

                fieldnames, matched_rows = _stream_zip_filter_mt(zip_bytes)
                _write_bronze_csv(local_target, fieldnames, matched_rows)

                logger.info(
                    f"[{self.source_id}] Ano {year}: {len(matched_rows):,} focos de MT "
                    f"→ {local_target.name}"
                )

                manifest = self._create_manifest(local_target, url)
                manifest.record_count = len(matched_rows)
                manifest.save(self.manifest_dir)
                results.append((local_target, manifest))

            except Exception as exc:
                logger.error(f"[{self.source_id}] Erro ao processar ano {year}: {exc}")

        return results

    # ─── Ingestão Mensal ──────────────────────────────────────────────────────

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
                    fieldnames, matched_rows = _stream_zip_filter_mt(zip_bytes)
                else:
                    # CSV stream direto (sem ler tudo em memória)
                    text_stream = io.TextIOWrapper(resp, encoding="utf-8", errors="ignore")
                    reader = csv.DictReader(text_stream)
                    fieldnames = list(reader.fieldnames or [])
                    for row in reader:
                        if _is_mt_row(row):
                            matched_rows.append(row)

            _write_bronze_csv(local_target, fieldnames, matched_rows)

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

    def ingest(
        self,
        months: list[str] | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        **kwargs: Any,
    ) -> list[tuple[Path, IngestionManifest]]:
        """
        Executa a ingestão mensal para os meses solicitados (formato YYYYMM) ou range de anos.

        Args:
            months: Lista de meses YYYYMM explícitos. Se None, usa year_from/year_to
                    ou os meses mais recentes disponíveis.
            year_from: Filtra meses a partir deste ano (inclusive).
            year_to: Filtra meses até este ano (inclusive).
        """
        available = self.list_available_files()
        if not available:
            logger.warning(f"[{self.source_id}] Nenhum arquivo disponível no INPE.")
            return []

        target_files: list[str] = []

        if months:
            for m in months:
                matching = [f for f in available if f"_{m}." in f]
                target_files.extend(matching)
        elif year_from is not None or year_to is not None:
            # Range de anos
            for f in available:
                m = re.search(r"_(\d{4})\d{2}\.", f)
                if not m:
                    continue
                y = int(m.group(1))
                if year_from is not None and y < year_from:
                    continue
                if year_to is not None and y > year_to:
                    continue
                target_files.append(f)
        else:
            # Padrão: ano atual e anterior
            current_year = datetime.now(tz=timezone.utc).year
            target_years = [str(current_year - 1), str(current_year)]
            target_files = [f for f in available if any(f"_{y}" in f for y in target_years)]
            if not target_files:
                target_files = available[-6:]

        results: list[tuple[Path, IngestionManifest]] = []
        for fn in sorted(target_files):
            res = self.download_and_filter_month(fn)
            if res:
                results.append(res)

        return results
