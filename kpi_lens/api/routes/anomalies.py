"""Anomaly event endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from kpi_lens.db.repository import KPIRepository

router = APIRouter()
_repo = KPIRepository()


@router.get("/")
def list_anomalies(
    days_back: int = Query(default=30),
    severity_floor: float = Query(default=0.3),
) -> list[dict[str, Any]]:
    return _repo.get_recent_anomalies(
        days_back=days_back,
        severity_floor=severity_floor,
    )


@router.post("/{anomaly_id}/acknowledge")
def acknowledge_anomaly(
    anomaly_id: int,
    acknowledged_by: str = Query(default="dashboard"),
) -> dict[str, Any]:
    success = _repo.acknowledge_anomaly(anomaly_id, acknowledged_by=acknowledged_by)
    if not success:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")
    return {"acknowledged": True, "anomaly_id": anomaly_id}
