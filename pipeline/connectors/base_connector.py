"""
pipeline/connectors/base_connector.py
======================================
Classe base para todos os conectores de fontes de dados do RootL Atlas.

Responsabilidades:
- Download robusto com retry e backoff exponencial
- Cálculo e verificação de hash SHA-256 (integridade)
- Gravação do manifesto de metadados (rastreabilidade)
- Upload para MinIO (Bronze imutável)
- Interface assíncrona com httpx
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import httpx
from botocore.exceptions import ClientError
from loguru import logger
from tenacity import (
    after_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class IngestionManifest:
    """Manifesto de metadados gerado a cada operação de ingestão."""

    def __init__(
        self,
        source_id: str,
        url: str,
        local_path: Path,
        file_hash: str,
        extracted_at: datetime,
        file_size_bytes: int,
        record_count: int | None = None,
        catalog_version: str = "1.0",
    ) -> None:
        self.source_id = source_id
        self.url = url
        self.local_path = str(local_path)
        self.file_hash = file_hash
        self.hash_algorithm = "sha256"
        self.extracted_at = extracted_at.isoformat()
        self.file_size_bytes = file_size_bytes
        self.record_count = record_count
        self.catalog_version = catalog_version
        self.manifest_schema_version = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__

    def save(self, manifest_dir: Path) -> Path:
        """Persiste o manifesto em JSON no diretório de manifestos."""
        manifest_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fname = f"{self.source_id}_{ts}.manifest.json"
        target = manifest_dir / fname
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"Manifesto gravado: {target}")
        return target


class BaseConnector(ABC):
    """
    Classe base abstrata para conectores de fontes de dados.

    Cada fonte de dados (IBGE, INEP, DATASUS, etc.) implementa
    uma subclasse que sobrescreve os métodos abstratos.
    """

    def __init__(
        self,
        source_id: str,
        bronze_base_path: str,
        minio_endpoint: str | None = None,
        minio_access_key: str | None = None,
        minio_secret_key: str | None = None,
        minio_bucket: str = "atlas-bronze",
        minio_secure: bool = False,
    ) -> None:
        self.source_id = source_id
        self.bronze_base_path = Path(bronze_base_path)
        self.bronze_path = self.bronze_base_path / self.source_id
        self.manifest_dir = self.bronze_base_path / "manifests"
        self.manifests_path = self.manifest_dir

        # MinIO client (opcional no desenvolvimento local)
        self._s3_client = None
        if minio_endpoint and minio_access_key and minio_secret_key:
            protocol = "https" if minio_secure else "http"
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=f"{protocol}://{minio_endpoint}",
                aws_access_key_id=minio_access_key,
                aws_secret_access_key=minio_secret_key,
            )
            self._minio_bucket = minio_bucket

    @classmethod
    def from_env(cls, source_id: str, **kwargs: Any) -> "BaseConnector":
        """Cria conector a partir de variáveis de ambiente."""
        return cls(
            source_id=source_id,
            bronze_base_path=os.getenv("LAKEHOUSE_PATH", "/data"),
            minio_endpoint=os.getenv("MINIO_ENDPOINT"),
            minio_access_key=os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER"),
            minio_secret_key=os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD"),
            minio_bucket=os.getenv("MINIO_BUCKET_BRONZE", "atlas-bronze"),
            minio_secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            **kwargs,
        )

    # ─────────────────────────────────────────────────────────
    # Métodos abstratos — implementar em cada conector
    # ─────────────────────────────────────────────────────────

    @abstractmethod
    def get_download_url(self, **kwargs: Any) -> str:
        """Retorna a URL de download para o período/escopo solicitado."""
        ...

    @abstractmethod
    def get_local_filename(self, url: str, **kwargs: Any) -> str:
        """Retorna o nome do arquivo local a ser gravado no Bronze."""
        ...

    @abstractmethod
    def validate_raw_file(self, local_path: Path) -> bool:
        """Validação mínima do arquivo bruto (ex: cabeçalho, tipo MIME)."""
        ...

    # ─────────────────────────────────────────────────────────
    # Métodos concretos
    # ─────────────────────────────────────────────────────────

    @staticmethod
    def compute_sha256(file_path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
        """Calcula SHA-256 do arquivo em blocos para suportar arquivos grandes."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                h.update(chunk)
        return h.hexdigest()

    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=5, max=120),
        stop=stop_after_attempt(5),
        after=after_log(logger, "WARNING"),
    )
    def _download_with_retry(
        self,
        url: str,
        dest: Path,
        expected_hash: str | None = None,
        chunk_size: int = 8 * 1024 * 1024,
    ) -> Path:
        """
        Download com retry exponencial e verificação de hash opcional.

        Args:
            url: URL de origem
            dest: caminho local de destino
            expected_hash: SHA-256 esperado (None = sem verificação)
            chunk_size: tamanho do bloco de leitura em bytes

        Returns:
            Path do arquivo baixado
        """
        dest.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"[{self.source_id}] Iniciando download: {url}")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        try:
            ssl_ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except Exception:
            pass

        with httpx.stream("GET", url, headers=headers, verify=ssl_ctx, follow_redirects=True, timeout=300.0) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=chunk_size):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        logger.debug(f"  {pct:.1f}% ({downloaded:,}/{total:,} bytes)")

        file_hash = self.compute_sha256(dest)
        logger.info(f"[{self.source_id}] SHA-256: {file_hash}")

        if expected_hash and file_hash != expected_hash:
            dest.unlink(missing_ok=True)
            raise ValueError(
                f"Hash inválido para {url}. "
                f"Esperado: {expected_hash}, obtido: {file_hash}"
            )

        return dest

    def _upload_to_minio(self, local_path: Path, object_key: str) -> None:
        """Envia o arquivo para o bucket Bronze do MinIO."""
        if self._s3_client is None:
            logger.debug("MinIO não configurado — pulando upload.")
            return

        try:
            self._s3_client.upload_file(
                str(local_path),
                self._minio_bucket,
                object_key,
            )
            logger.info(
                f"[{self.source_id}] Upload MinIO: "
                f"s3://{self._minio_bucket}/{object_key}"
            )
        except ClientError as e:
            logger.error(f"[{self.source_id}] Erro no upload MinIO: {e}")
            raise

    def _create_manifest(self, local_path: Path, url: str) -> IngestionManifest:
        """Cria e retorna uma instância de IngestionManifest para o arquivo."""
        file_hash = self.compute_sha256(local_path) if local_path.exists() else ""
        return IngestionManifest(
            source_id=self.source_id,
            url=url,
            local_path=local_path,
            file_hash=file_hash,
            extracted_at=datetime.now(timezone.utc),
            file_size_bytes=local_path.stat().st_size if local_path.exists() else 0,
        )

    def ingest(self, **kwargs: Any) -> tuple[Path, IngestionManifest]:
        """
        Executa o ciclo completo de ingestão:
        1. Resolve URL
        2. Define caminho local
        3. Baixa o arquivo (com retry)
        4. Valida o arquivo bruto
        5. Calcula hash
        6. Envia para MinIO
        7. Grava manifesto

        Returns:
            Tupla (caminho_local, manifesto)
        """
        url = self.get_download_url(**kwargs)
        filename = self.get_local_filename(url, **kwargs)
        local_path = self.bronze_base_path / self.source_id / filename

        # Verifica se já foi baixado (idempotência)
        if local_path.exists():
            logger.info(
                f"[{self.source_id}] Arquivo já existe: {local_path}. "
                "Verificando hash..."
            )
            file_hash = self.compute_sha256(local_path)
        else:
            local_path = self._download_with_retry(url=url, dest=local_path)
            file_hash = self.compute_sha256(local_path)

        # Validação do arquivo bruto
        if not self.validate_raw_file(local_path):
            raise ValueError(
                f"[{self.source_id}] Arquivo falhou na validação: {local_path}"
            )

        # Upload para MinIO
        object_key = f"{self.source_id}/{filename}"
        self._upload_to_minio(local_path, object_key)

        # Manifesto de rastreabilidade
        manifest = IngestionManifest(
            source_id=self.source_id,
            url=url,
            local_path=local_path,
            file_hash=file_hash,
            extracted_at=datetime.now(timezone.utc),
            file_size_bytes=local_path.stat().st_size,
        )
        manifest.save(self.manifest_dir)

        logger.success(
            f"[{self.source_id}] Ingestão concluída. "
            f"Arquivo: {local_path} | {local_path.stat().st_size:,} bytes"
        )
        return local_path, manifest
