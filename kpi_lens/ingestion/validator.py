"""
Pydantic v2 validation models for inbound KPI records.

Validation happens at the ingestion boundary — after the loader parses the file
and before the repository writes to the database. Bad records are rejected with
structured errors written to the ingestion_audit table, never silently dropped.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from pydantic import BaseModel, field_validator, model_validator

from kpi_lens.kpis.definitions import KPI_BY_NAME


class InboundKPIRecord(BaseModel):
    """Validated representation of one row from an ingestion file."""

    kpi_name: str
    period_start: date
    period_end: date
    value: float
    unit: str
    entity: str = "global"
    source: str

    @field_validator("kpi_name")
    @classmethod
    def kpi_must_be_registered(cls, v: str) -> str:
        if v not in KPI_BY_NAME:
            raise ValueError(
                f"Unknown KPI name '{v}'. Must be one of: {sorted(KPI_BY_NAME)}"
            )
        return v

    @field_validator("value")
    @classmethod
    def value_must_be_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("KPI value must be a finite number")
        return v

    @model_validator(mode="after")
    def period_end_after_start(self) -> InboundKPIRecord:
        if self.period_end < self.period_start:
            raise ValueError("period_end must be >= period_start")
        return self


class ValidationResult(BaseModel):
    """Summary of validating a batch of inbound records."""

    accepted: list[InboundKPIRecord]
    rejected: list[dict[str, Any]]  # {"record": ..., "error": "..."}
    total_received: int

    @property
    def accepted_count(self) -> int:
        return len(self.accepted)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


def validate_batch(records: list[dict[str, Any]]) -> ValidationResult:
    """
    Validate a batch of raw record dicts. Returns accepted records and
    structured rejection details for audit logging.
    """
    accepted: list[InboundKPIRecord] = []
    rejected: list[dict[str, Any]] = []

    for raw in records:
        try:
            accepted.append(InboundKPIRecord.model_validate(raw))
        except ValueError as exc:
            rejected.append({"record": raw, "error": str(exc)})

    return ValidationResult(
        accepted=accepted,
        rejected=rejected,
        total_received=len(records),
    )
