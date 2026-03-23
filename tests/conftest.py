"""
Shared fixtures for the KPI-Lens test suite.

All fixtures here are available to every test without explicit import.
Key fixture contracts:
  - db_session: in-memory SQLite, fully isolated between tests
  - mock_anthropic: patches the Anthropic client — no real API calls
  - sample_kpi_df: 60 rows of realistic weekly OTIF data for detector tests
"""

from __future__ import annotations

import os

# Must be set before any kpi_lens module that reads Settings() is imported.
# The unit tests never call the real Anthropic API — the mock_anthropic fixture
# intercepts all calls. This value is a placeholder so pydantic-settings
# does not raise a validation error when the module is first imported in CI.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key-for-ci-only")

from datetime import date, timedelta
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from kpi_lens.db.schema import Base


@pytest.fixture
def db_session() -> Session:
    """Fully isolated in-memory SQLite session. Dropped after each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture
def mock_anthropic(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """
    Patches the Anthropic SDK client so no real API call is made.
    Returns a MagicMock that can be inspected to assert call arguments.
    """
    mock = MagicMock()
    mock.messages.create.return_value = MagicMock(
        content=[
            MagicMock(text="Mock LLM narrative: OTIF declined due to supplier delays.")
        ],
        usage=MagicMock(input_tokens=150, output_tokens=80),
    )
    monkeypatch.setattr("kpi_lens.llm.client.anthropic.Anthropic", lambda **_: mock)
    return mock


@pytest.fixture
def sample_kpi_df() -> pd.DataFrame:
    """
    60 weeks of synthetic weekly OTIF data in the expected DataFrame schema.
    Values are normally distributed around 96.0 (green territory) so detectors
    trained on this fixture have a well-defined baseline.
    """
    rng = np.random.default_rng(42)
    n = 60
    start = date.today() - timedelta(weeks=n)
    rows = []
    for i in range(n):
        period_start = start + timedelta(weeks=i)
        rows.append(
            {
                "period_start": period_start,
                "period_end": period_start + timedelta(days=6),
                "value": float(rng.normal(96.0, 1.5)),
                "entity": "global",
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def sample_kpi_df_with_spike(sample_kpi_df: pd.DataFrame) -> pd.DataFrame:
    """Same as sample_kpi_df but with a clear spike in the last 2 rows."""
    df = sample_kpi_df.copy()
    df.loc[df.index[-1], "value"] = 78.0  # Far below red threshold (85%)
    df.loc[df.index[-2], "value"] = 81.0
    return df
