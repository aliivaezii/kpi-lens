"""Integration tests for the /api/kpis/* endpoints."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_snapshot_returns_dict(client: AsyncClient) -> None:
    resp = await client.get("/api/kpis/snapshot")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


@pytest.mark.anyio
async def test_snapshot_empty_when_no_data(client: AsyncClient) -> None:
    resp = await client.get("/api/kpis/snapshot")
    assert resp.json() == {}


@pytest.mark.anyio
async def test_series_returns_404_for_unknown_kpi(client: AsyncClient) -> None:
    today = date.today()
    resp = await client.get(
        "/api/kpis/nonexistent_kpi/series",
        params={"start": str(today - timedelta(days=30)), "end": str(today)},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_series_returns_list_for_known_kpi(client: AsyncClient) -> None:
    today = date.today()
    resp = await client.get(
        "/api/kpis/otif/series",
        params={"start": str(today - timedelta(days=30)), "end": str(today)},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_entities_returns_404_for_unknown_kpi(client: AsyncClient) -> None:
    today = date.today()
    resp = await client.get(
        "/api/kpis/bad_kpi/entities",
        params={"start": str(today - timedelta(days=30)), "end": str(today)},
    )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_entities_returns_list_for_known_kpi(client: AsyncClient) -> None:
    today = date.today()
    resp = await client.get(
        "/api/kpis/otif/entities",
        params={"start": str(today - timedelta(days=30)), "end": str(today)},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.anyio
async def test_benchmarks_returns_404_for_unknown_kpi(client: AsyncClient) -> None:
    resp = await client.get("/api/kpis/not_a_kpi/benchmarks")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_benchmarks_returns_dict_for_known_kpi(client: AsyncClient) -> None:
    resp = await client.get("/api/kpis/otif/benchmarks")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
