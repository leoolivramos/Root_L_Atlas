"""
api/config.py — Configuração centralizada via Pydantic Settings
"""
from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Banco de dados
    database_url: str = Field(
        default="postgresql+asyncpg://atlas:123456@localhost:5432/rootl_atlas"
    )

    # Pool de conexões
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20
    db_pool_max_inactive_connection_lifetime: float = 300.0

    # CORS
    cors_origins: list[str] | str = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    @field_validator("cors_origins")
    @classmethod
    def parse_cors(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed]
            except Exception:
                pass
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # API
    api_title: str = "RootL Atlas API"
    api_version: str = "1.0.0"
    api_description: str = "Plataforma geoespacial de inteligência territorial — Mato Grosso"
    log_level: str = "INFO"

    # Limites de segurança
    max_features_geojson: int = 500   # Máximo de feições em resposta GeoJSON
    tile_cache_max_age: int = 3600    # Cache de tiles (segundos)

    # Escopo territorial
    territory_state: str = "MT"
    territory_state_ibge_code: str = "51"

    # Zoom guards para MVT
    mvt_zoom_municipios_min: int = 5
    mvt_zoom_setores_min: int = 8
    mvt_zoom_pontos_min: int = 8     # Escolas, saúde (visíveis mais cedo)


settings = Settings()
