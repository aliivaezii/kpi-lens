"""Integration tests for the /api/llm/chat endpoint."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_chat_returns_200(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/llm/chat",
        json={"message": "What is OTIF?", "history": []},
    )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_chat_response_has_response_field(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/llm/chat",
        json={"message": "Summarise the KPI dashboard.", "history": []},
    )
    data = resp.json()
    assert "response" in data
    assert isinstance(data["response"], str)
    assert len(data["response"]) > 0
