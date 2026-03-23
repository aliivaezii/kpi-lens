"""KPI snapshot, time-series, entity breakdown, and benchmark endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from kpi_lens.db.repository import KPIRepository
from kpi_lens.kpis.definitions import KPI_BY_NAME
from kpi_lens.kpis.snapshot import enrich_snapshot

router = APIRouter()
_repo = KPIRepository()

# Required date query params — no default, so Query() inside Annotated is valid.
_DateQ = Annotated[date, Query()]


@router.get("/snapshot")
def get_snapshot() -> dict[str, Any]:
    raw = _repo.get_latest_snapshot()
    return enrich_snapshot(raw)


@router.get("/{kpi_name}/series")
def get_series(
    kpi_name: str,
    start: _DateQ,
    end: _DateQ,
    entity: str = Query(default="global"),
) -> list[dict[str, Any]]:
    if kpi_name not in KPI_BY_NAME:
        raise HTTPException(status_code=404, detail=f"Unknown KPI: {kpi_name}")
    df = _repo.get_kpi_series(kpi_name, start, end, entity=entity)
    return df.to_dict(orient="records")  # type: ignore[return-value]


@router.get("/{kpi_name}/entities")
def get_entity_breakdown(
    kpi_name: str,
    start: _DateQ,
    end: _DateQ,
) -> list[dict[str, Any]]:
    if kpi_name not in KPI_BY_NAME:
        raise HTTPException(status_code=404, detail=f"Unknown KPI: {kpi_name}")
    return _repo.get_entity_breakdown(kpi_name, start, end)


@router.get("/{kpi_name}/benchmarks")
def get_benchmarks(kpi_name: str) -> dict[str, Any]:
    if kpi_name not in KPI_BY_NAME:
        raise HTTPException(status_code=404, detail=f"Unknown KPI: {kpi_name}")
    return _repo.get_benchmarks(kpi_name)
