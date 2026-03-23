"""
Shared fixtures for the FastAPI integration test suite.

Integration tests use an in-memory SQLite database and a mocked Anthropic
client — no real network calls are made. The FastAPI app dependency on
KPIRepository is overridden so every test gets a clean, isolated DB.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key-for-ci-only")

from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from kpi_lens.api.main import app
from kpi_lens.db.repository import KPIRepository
from kpi_lens.db.schema import Base


def _make_memory_repo() -> KPIRepository:
    # StaticPool ensures every engine.connect() call returns the SAME underlying
    # connection, so Base.metadata.create_all() and subsequent query sessions all
    # see the same in-memory database. Without it, QueuePool can hand out a fresh
    # connection whose :memory: database is empty, causing "no such table" errors.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    repo = KPIRepository("sqlite:///:memory:")
    repo._engine = engine
    Base.metadata.create_all(engine)
    return repo


@pytest_asyncio.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """
    AsyncClient wired to the FastAPI app with an in-memory repo and mocked LLM.

    Each test gets a fresh in-memory DB so state never leaks between tests.
    follow_redirects=True is required because FastAPI redirects trailing-slash-less
    paths (e.g. GET /api/anomalies → 307 → /api/anomalies/) by default.
    """
    repo = _make_memory_repo()

    import kpi_lens.api.routes.anomalies as anomalies_mod
    import kpi_lens.api.routes.kpis as kpis_mod
    import kpi_lens.api.routes.llm as llm_mod
    import kpi_lens.api.routes.reports as reports_mod

    monkeypatch.setattr(kpis_mod, "_repo", repo)
    monkeypatch.setattr(anomalies_mod, "_repo", repo)
    monkeypatch.setattr(reports_mod, "_repo", repo)

    mock_analyst = MagicMock()
    mock_analyst.chat.return_value = "Mock analyst response for integration tests."
    monkeypatch.setattr(llm_mod, "_analyst", mock_analyst)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        yield ac
