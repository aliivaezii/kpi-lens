"""Unit tests for KPIRepository using an in-memory SQLite database."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from kpi_lens.db.repository import KPIRepository
from kpi_lens.db.schema import Base, KPIRecord


@pytest.fixture
def repo() -> KPIRepository:
    """Fresh in-memory repository with schema created — isolated per test."""
    r = KPIRepository("sqlite:///:memory:")
    Base.metadata.create_all(r._engine)
    return r


def _insert_kpi(
    repo: KPIRepository,
    kpi_name: str = "otif",
    value: float = 95.0,
    entity: str = "global",
    days_ago: int = 0,
) -> KPIRecord:
    from sqlalchemy.orm import Session

    today = date.today()
    record = KPIRecord(
        kpi_name=kpi_name,
        period_start=today - timedelta(days=7 + days_ago),
        period_end=today - timedelta(days=days_ago),
        value=value,
        unit="%",
        entity=entity,
        source="test",
    )
    with Session(repo._engine) as session:
        session.add(record)
        session.commit()
    return record


# ── get_latest_value ──────────────────────────────────────────────────────────


def test_get_latest_value_returns_none_when_empty(repo: KPIRepository) -> None:
    assert repo.get_latest_value("otif") is None


def test_get_latest_value_returns_most_recent(repo: KPIRepository) -> None:
    _insert_kpi(repo, value=94.0, days_ago=14)
    _insert_kpi(repo, value=96.5, days_ago=0)
    result = repo.get_latest_value("otif")
    assert result == pytest.approx(96.5)


# ── get_kpi_series ────────────────────────────────────────────────────────────


def test_get_kpi_series_returns_empty_df_when_no_data(repo: KPIRepository) -> None:
    df = repo.get_kpi_series("otif", date(2024, 1, 1), date(2024, 12, 31))
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 0


def test_get_kpi_series_returns_correct_rows(repo: KPIRepository) -> None:
    _insert_kpi(repo, value=95.0, days_ago=0)
    _insert_kpi(repo, value=93.0, days_ago=14)
    start = date.today() - timedelta(days=30)
    df = repo.get_kpi_series("otif", start, date.today())
    assert len(df) == 2
    assert "value" in df.columns


def test_get_kpi_series_filters_by_entity(repo: KPIRepository) -> None:
    _insert_kpi(repo, entity="global", value=95.0)
    _insert_kpi(repo, entity="supplier:A", value=88.0)
    start = date.today() - timedelta(days=30)
    df = repo.get_kpi_series("otif", start, date.today(), entity="global")
    assert len(df) == 1
    assert float(df["value"].iloc[0]) == pytest.approx(95.0)


# ── get_latest_snapshot ───────────────────────────────────────────────────────


def test_get_latest_snapshot_returns_dict(repo: KPIRepository) -> None:
    result = repo.get_latest_snapshot()
    assert isinstance(result, dict)


def test_get_latest_snapshot_contains_inserted_kpi(repo: KPIRepository) -> None:
    _insert_kpi(repo, kpi_name="otif", value=96.0)
    snapshot = repo.get_latest_snapshot()
    assert "otif" in snapshot
    assert snapshot["otif"]["value"] == pytest.approx(96.0)


# ── get_recent_anomalies ──────────────────────────────────────────────────────


def test_get_recent_anomalies_returns_empty_list(repo: KPIRepository) -> None:
    result = repo.get_recent_anomalies()
    assert result == []


# ── get_anomaly ───────────────────────────────────────────────────────────────


def test_get_anomaly_returns_none_for_unknown_id(repo: KPIRepository) -> None:
    assert repo.get_anomaly(9999) is None


# ── get_entity_breakdown ──────────────────────────────────────────────────────


def test_get_entity_breakdown_returns_list(repo: KPIRepository) -> None:
    _insert_kpi(repo, entity="supplier:A", value=88.0)
    _insert_kpi(repo, entity="supplier:B", value=92.0)
    start = date.today() - timedelta(days=30)
    result = repo.get_entity_breakdown("otif", start, date.today())
    assert isinstance(result, list)


# ── get_benchmarks ────────────────────────────────────────────────────────────


def test_get_benchmarks_returns_empty_dict_when_no_data(repo: KPIRepository) -> None:
    result = repo.get_benchmarks("otif")
    assert result == {}


# ── enqueue_report ────────────────────────────────────────────────────────────


def test_enqueue_report_returns_job_id_string(repo: KPIRepository) -> None:
    job_id = repo.enqueue_report(
        anomaly_ids=[1, 2, 3],
        recipients=["analyst@company.com"],
        triggered_by="test",
    )
    assert isinstance(job_id, str)
    assert "report" in job_id
    assert "3anomalies" in job_id
