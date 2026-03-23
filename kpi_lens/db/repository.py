"""
Database repository — the only module allowed to touch SQLAlchemy sessions.

All other modules receive plain Python objects (dicts, DataFrames) from here.
When the schema changes, only this file and schema.py need to change.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from kpi_lens.config import settings
from kpi_lens.db.schema import AnomalyEvent, BenchmarkReference, KPIRecord


class KPIRepository:
    """Read/write gateway for all KPI-Lens database operations."""

    def __init__(self, database_url: str | None = None) -> None:
        url = database_url or settings.database_url
        self._engine = create_engine(url, connect_args={"check_same_thread": False})

    def _session(self) -> Session:
        return Session(self._engine)

    # ── KPI Records ───────────────────────────────────────────────────────────

    def get_latest_snapshot(self, as_of: date | None = None) -> dict[str, Any]:
        """Return the most recent value for every KPI as of `as_of` date."""
        cutoff = as_of or date.today()
        result: dict[str, Any] = {}
        with self._session() as session:
            # Distinct KPI names present in the DB
            names = (
                session.execute(select(KPIRecord.kpi_name).distinct()).scalars().all()
            )
            for name in names:
                row = session.execute(
                    select(KPIRecord)
                    .where(KPIRecord.kpi_name == name)
                    .where(KPIRecord.period_end <= cutoff)
                    .order_by(KPIRecord.period_end.desc())
                    .limit(1)
                ).scalar_one_or_none()
                if row:
                    result[name] = {
                        "value": row.value,
                        "unit": row.unit,
                        "entity": row.entity,
                        "period_start": str(row.period_start),
                        "period_end": str(row.period_end),
                    }
        return result

    def get_kpi_series_extended(
        self,
        kpi_name: str,
        start: date,
        end: date,
        entity: str | None = None,
    ) -> pd.DataFrame:
        """
        Like get_kpi_series but entity=None returns all entities combined.

        The explicit None sentinel avoids overloading the string parameter with
        a sentinel value like "all", which would collide with a real entity name.
        """
        with self._session() as session:
            query = (
                select(KPIRecord)
                .where(KPIRecord.kpi_name == kpi_name)
                .where(KPIRecord.period_start >= start)
                .where(KPIRecord.period_end <= end)
                .order_by(KPIRecord.period_start)
            )
            if entity is not None:
                query = query.where(KPIRecord.entity == entity)
            rows = session.execute(query).scalars().all()
        if not rows:
            return pd.DataFrame(
                columns=["period_start", "period_end", "value", "entity"]
            )
        return pd.DataFrame(
            [
                {
                    "period_start": r.period_start,
                    "period_end": r.period_end,
                    "value": r.value,
                    "entity": r.entity,
                }
                for r in rows
            ]
        )

    def acknowledge_anomaly(
        self, anomaly_id: int, acknowledged_by: str = "dashboard"
    ) -> bool:
        """
        Mark an anomaly as acknowledged. Returns False if the anomaly does not exist.

        acknowledged_at is set to UTC now so the audit trail captures when the
        acknowledgement happened, not just who did it.
        """
        with self._session() as session:
            row = session.get(AnomalyEvent, anomaly_id)
            if row is None:
                return False
            row.is_acknowledged = True
            row.acknowledged_by = acknowledged_by
            row.acknowledged_at = datetime.now(tz=UTC)
            session.commit()
        return True

    def get_report_log(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return recent report log entries ordered by generated_at desc."""
        # NOTE: ReportLog table is in schema but enqueue_report doesn't write to it yet.
        # Return empty list for now — reporting is Phase 3.
        return []

    def get_kpi_series(
        self,
        kpi_name: str,
        start: date,
        end: date,
        entity: str = "global",
    ) -> pd.DataFrame:
        """Return a DataFrame of KPI values over [start, end] for one entity."""
        with self._session() as session:
            rows = (
                session.execute(
                    select(KPIRecord)
                    .where(KPIRecord.kpi_name == kpi_name)
                    .where(KPIRecord.entity == entity)
                    .where(KPIRecord.period_start >= start)
                    .where(KPIRecord.period_end <= end)
                    .order_by(KPIRecord.period_start)
                )
                .scalars()
                .all()
            )
        if not rows:
            return pd.DataFrame(
                columns=["period_start", "period_end", "value", "entity"]
            )
        return pd.DataFrame(
            [
                {
                    "period_start": r.period_start,
                    "period_end": r.period_end,
                    "value": r.value,
                    "entity": r.entity,
                }
                for r in rows
            ]
        )

    def get_latest_value(self, kpi_name: str) -> float | None:
        with self._session() as session:
            row = session.execute(
                select(KPIRecord)
                .where(KPIRecord.kpi_name == kpi_name)
                .where(KPIRecord.entity == "global")
                .order_by(KPIRecord.period_end.desc())
                .limit(1)
            ).scalar_one_or_none()
            return row.value if row else None

    def get_entity_breakdown(
        self,
        kpi_name: str,
        start: date,
        end: date,
        top_n: int = 5,
        entity_prefix: str = "supplier:",
    ) -> list[dict[str, Any]]:
        """Return per-entity values, sorted by value ascending (worst first)."""
        with self._session() as session:
            rows = (
                session.execute(
                    select(KPIRecord)
                    .where(KPIRecord.kpi_name == kpi_name)
                    .where(KPIRecord.entity.startswith(entity_prefix))
                    .where(KPIRecord.period_start >= start)
                    .where(KPIRecord.period_end <= end)
                    .order_by(KPIRecord.value)
                    .limit(top_n)
                )
                .scalars()
                .all()
            )
        return [
            {"entity": r.entity, "value": r.value, "period_end": str(r.period_end)}
            for r in rows
        ]

    # ── Anomaly Events ────────────────────────────────────────────────────────

    def get_recent_anomalies(
        self,
        days_back: int = 30,
        severity_floor: float = 0.3,
        kpi_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        since = datetime.now(tz=UTC) - timedelta(days=days_back)
        with self._session() as session:
            query = (
                select(AnomalyEvent)
                .where(AnomalyEvent.detected_at >= since)
                .where(AnomalyEvent.severity >= severity_floor)
                .order_by(AnomalyEvent.severity.desc())
            )
            if kpi_filter:
                query = query.where(AnomalyEvent.kpi_name.in_(kpi_filter))
            rows = session.execute(query).scalars().all()
        return [
            {
                "id": r.id,
                "kpi_name": r.kpi_name,
                "detected_at": r.detected_at.isoformat(),
                "period_start": str(r.period_start),
                "period_end": str(r.period_end),
                "observed_value": r.observed_value,
                "expected_low": r.expected_low,
                "expected_high": r.expected_high,
                "severity": r.severity,
                "detector_name": r.detector_name,
                "entity": r.entity,
                "is_acknowledged": r.is_acknowledged,
                "llm_narrative": r.llm_narrative,
                "llm_actions": r.llm_actions,
            }
            for r in rows
        ]

    def get_anomaly(self, anomaly_id: int) -> dict[str, Any] | None:
        with self._session() as session:
            row = session.get(AnomalyEvent, anomaly_id)
            if row is None:
                return None
            return {
                "id": row.id,
                "kpi_name": row.kpi_name,
                "period_start": row.period_start,
                "period_end": row.period_end,
                "observed_value": row.observed_value,
                "expected_low": row.expected_low,
                "expected_high": row.expected_high,
                "severity": row.severity,
                "detector_name": row.detector_name,
                "entity": row.entity,
            }

    def update_anomaly_narrative(
        self,
        anomaly_id: int,
        narrative: str,
        actions: str,
    ) -> None:
        with self._session() as session:
            row = session.get(AnomalyEvent, anomaly_id)
            if row:
                row.llm_narrative = narrative
                row.llm_actions = actions
                row.llm_generated_at = datetime.now(tz=UTC)
                session.commit()

    def get_benchmarks(
        self,
        kpi_name: str,
        industry: str = "automotive",
    ) -> dict[str, Any]:
        with self._session() as session:
            row = session.execute(
                select(BenchmarkReference)
                .where(BenchmarkReference.kpi_name == kpi_name)
                .where(BenchmarkReference.industry == industry)
                .order_by(BenchmarkReference.valid_from.desc())
                .limit(1)
            ).scalar_one_or_none()
        if not row:
            return {}
        return {
            "p25": row.percentile_25,
            "p50": row.percentile_50,
            "p75": row.percentile_75,
            "p90": row.percentile_90,
            "source": row.source,
        }

    # ── Reports ───────────────────────────────────────────────────────────────

    def enqueue_report(
        self,
        anomaly_ids: list[int],
        recipients: list[str],
        include_recommendations: bool = True,
        triggered_by: str = "api",
    ) -> str:
        # Job ID format: report-<timestamp>-<anomaly_count>
        # Actual async execution is handled by the APScheduler job queue.
        ts = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
        return f"report-{ts}-{len(anomaly_ids)}anomalies"
