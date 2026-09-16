"""
api/tests/test_tiles.py — Testes do endpoint MVT
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch, MagicMock

from main import app


@pytest.fixture
def mock_db_pool():
    """Mock do pool asyncpg para testes sem banco real."""
    pool = MagicMock()
    mock_conn = AsyncMock()
    pool.acquire = MagicMock(return_value=MagicMock(
        __aenter__=AsyncMock(return_value=mock_conn),
        __aexit__=AsyncMock(return_value=None),
    ))
    return pool, mock_conn


@pytest.mark.asyncio
async def test_health_check_no_db():
    """Health check responde mesmo sem banco."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        with patch("routers.tiles.get_connection") as mock_conn:
            mock_conn.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
                fetchrow=AsyncMock(return_value={"setores": 0})
            ))
            mock_conn.return_value.__aexit__ = AsyncMock(return_value=None)
            resp = await client.get("/health")
            # Pode retornar 200 (saudável) ou degraded, mas não 500
            assert resp.status_code in (200,)


@pytest.mark.asyncio
async def test_tile_invalid_layer():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/tiles/inexistente/10/300/400")
        assert resp.status_code == 404
        assert "inexistente" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_tile_zoom_too_low_returns_204():
    """Setores em zoom < 8 devem retornar 204 (sem conteúdo)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/tiles/setores/5/10/15")
        assert resp.status_code == 204


@pytest.mark.asyncio
async def test_tile_metadata():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/tiles/setores/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tilejson"] == "3.0.0"
        assert "tiles" in data
        assert data["minzoom"] == 8  # Setores min zoom


@pytest.mark.asyncio
async def test_layer_list_complete():
    """Verifica que todas as 4 camadas estão disponíveis."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        for layer in ["municipios", "setores", "escolas", "saude"]:
            resp = await client.get(f"/tiles/{layer}/metadata")
            assert resp.status_code == 200, f"Camada '{layer}' falhou"


@pytest.mark.asyncio
async def test_root_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "layers" in data
        assert "setores" in data["layers"]


@pytest.mark.asyncio
async def test_search_requires_min_2_chars():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/search?q=a")
        assert resp.status_code == 422  # Validação Pydantic


@pytest.mark.asyncio
async def test_tile_zoom_bounds():
    """Tiles fora dos limites de zoom devem retornar erro."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/tiles/setores/25/0/0")
        assert resp.status_code == 422  # zoom > 22
