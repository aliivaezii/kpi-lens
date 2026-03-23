"""Integration tests for the /api/reports/enqueue endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_enqueue_report_returns_200(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/reports/enqueue",
        json={
            "anomaly_ids": [1, 2, 3],
            "recipients": ["analyst@company.com"],
            "triggered_by": "test",
        },
    )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_enqueue_report_returns_job_id(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/reports/enqueue",
        json={
            "anomaly_ids": [1],
            "recipients": ["a@b.com"],
            "triggered_by": "integration_test",
        },
    )
    data = resp.json()
    assert "job_id" in data
    assert "report" in data["job_id"]
