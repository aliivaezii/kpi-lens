"""Integration tests for the /api/anomalies/* endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_list_anomalies_returns_list(client: AsyncClient) -> None:
    resp = await client.get("/api/anomalies")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_list_anomalies_empty_when_no_data(client: AsyncClient) -> None:
    resp = await client.get("/api/anomalies")
    assert resp.json() == []


@pytest.mark.anyio
async def test_acknowledge_nonexistent_anomaly_returns_404(
    client: AsyncClient,
) -> None:
    resp = await client.post("/api/anomalies/99999/acknowledge")
    assert resp.status_code == 404
