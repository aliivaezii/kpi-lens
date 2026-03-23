"""Report enqueueing endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from kpi_lens.db.repository import KPIRepository

router = APIRouter()
_repo = KPIRepository()


class ReportRequest(BaseModel):
    anomaly_ids: list[int]
    recipients: list[str]
    include_recommendations: bool = True
    triggered_by: str = "api"


@router.post("/enqueue")
def enqueue_report(request: ReportRequest) -> dict[str, Any]:
    job_id = _repo.enqueue_report(
        anomaly_ids=request.anomaly_ids,
        recipients=request.recipients,
        include_recommendations=request.include_recommendations,
        triggered_by=request.triggered_by,
    )
    return {"job_id": job_id, "anomaly_count": len(request.anomaly_ids)}
