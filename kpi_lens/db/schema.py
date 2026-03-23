"""
SQLAlchemy 2.0 ORM models — the single source of truth for the database schema.

All migrations are derived from these models. No SQL is written anywhere else
in the codebase. Column names use snake_case to match pandas DataFrame columns
that flow in from the anomaly detection pipeline.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):  # type: ignore[misc]
    pass


class KPIRecord(Base):
    """A single KPI measurement for one entity over one time window."""

    __tablename__ = "kpi_records"
    __table_args__ = (
        UniqueConstraint("kpi_name", "period_start", "period_end", "entity"),
        Index("idx_kpi_records_name_period", "kpi_name", "period_start", "period_end"),
        Index("idx_kpi_records_entity", "entity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kpi_name: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    # entity allows drill-down by plant, SKU, or supplier without separate tables
    entity: Mapped[str] = mapped_column(String(128), nullable=False, default="global")
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    anomaly_events: Mapped[list[AnomalyEvent]] = relationship(
        back_populates="kpi_record", cascade="all, delete-orphan"
    )


class AnomalyEvent(Base):
    """
    A detected anomaly for a KPI at a specific time window.

    The `llm_narrative` and `llm_actions` columns are populated asynchronously
    by the LLM analyst — they may be NULL immediately after detection.
    """

    __tablename__ = "anomaly_events"
    __table_args__ = (
        CheckConstraint("severity BETWEEN 0.0 AND 1.0", name="chk_severity_range"),
        Index("idx_anomaly_events_kpi_detected", "kpi_name", "detected_at"),
        Index("idx_anomaly_events_severity", "severity"),
        # Partial index for the dashboard "unacknowledged" filter — fast lookup
        Index(
            "idx_anomaly_events_unack",
            "is_acknowledged",
            postgresql_where=text("is_acknowledged = FALSE"),
            sqlite_where=text("is_acknowledged = 0"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kpi_name: Mapped[str] = mapped_column(
        String(64), ForeignKey("kpi_records.kpi_name"), nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    expected_low: Mapped[float] = mapped_column(Float, nullable=False)
    expected_high: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[float] = mapped_column(Float, nullable=False)
    # Stores which detector(s) triggered: 'zscore', 'ensemble', etc.
    detector_name: Mapped[str] = mapped_column(String(64), nullable=False)
    entity: Mapped[str] = mapped_column(String(128), nullable=False, default="global")
    is_acknowledged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    acknowledged_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Populated asynchronously after detection — NULL until Claude has processed it
    llm_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_actions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    llm_generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    kpi_record: Mapped[KPIRecord] = relationship(back_populates="anomaly_events")


class BenchmarkReference(Base):
    """Industry benchmark percentiles for each KPI, sourced from public reports."""

    __tablename__ = "benchmark_references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kpi_name: Mapped[str] = mapped_column(String(64), nullable=False)
    industry: Mapped[str] = mapped_column(String(64), nullable=False)
    percentile_25: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentile_50: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentile_75: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentile_90: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(256), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class ReportLog(Base):
    """Audit trail for every generated report."""

    __tablename__ = "report_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    report_type: Mapped[str] = mapped_column(
        String(32),
        CheckConstraint("report_type IN ('weekly','monthly','adhoc','anomaly_alert')"),
        nullable=False,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_sent_to: Mapped[str | None] = mapped_column(Text, nullable=True)
    anomaly_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    triggered_by: Mapped[str] = mapped_column(String(64), nullable=False)


class IngestionAudit(Base):
    """One row per ingestion batch — used to track data freshness and errors."""

    __tablename__ = "ingestion_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    source_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    records_received: Mapped[int] = mapped_column(Integer, nullable=False)
    records_accepted: Mapped[int] = mapped_column(Integer, nullable=False)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_errors: Mapped[str | None] = mapped_column(Text, nullable=True)
