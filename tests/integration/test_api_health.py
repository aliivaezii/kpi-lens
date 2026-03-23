"""Integration tests for the /api/health endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_health_response_has_status_field(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    data = resp.json()
    assert "status" in data
