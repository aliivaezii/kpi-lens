"""LLM analyst chat endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from kpi_lens.db.repository import KPIRepository
from kpi_lens.llm.analyst import SupplyChainAnalyst

router = APIRouter()
_repo = KPIRepository()
_analyst = SupplyChainAnalyst(repo=_repo)


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []


@router.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    response = _analyst.chat(request.message, history=request.history)
    return {"response": response}
