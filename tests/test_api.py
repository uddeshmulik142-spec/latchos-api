from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models import ComplianceStatus, DocumentType


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_verify_credential_mock():
    # Mock out database pool and gate dispatch
    with patch("app.routes.credentials.get_pool") as mock_pool, \
         patch("app.routes.credentials.trigger_gate_barrier_action", new_callable=AsyncMock):

        mock_conn = AsyncMock()
        mock_pool.return_value.acquire.return_value.__aenter__.return_value = mock_conn

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            files = {
                "file": ("test.png", b"fake-image-bytes", "image/png"),
            }
            res = await client.post("/api/v1/verify-credential", files=files)
            assert res.status_code == 200
            data = res.json()
            assert data["verdict"] == "PASSED"
            assert data["document_type"] == "UK_DRIVING_LICENCE"


@pytest.mark.asyncio
async def test_unsupported_file_format():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        files = {
            "file": ("test.txt", b"plain text", "text/plain"),
        }
        res = await client.post("/api/v1/verify-credential", files=files)
        assert res.status_code == 400
        assert "Unsupported format" in res.json()["detail"]
