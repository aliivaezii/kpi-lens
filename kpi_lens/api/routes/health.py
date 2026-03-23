from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, Any]:
    return {"status": "ok", "service": "kpi-lens-api"}
