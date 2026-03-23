"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from kpi_lens.api.routes import anomalies, health, kpis, llm, reports

app = FastAPI(
    title="KPI-Lens API",
    description="Supply chain KPI anomaly detection and LLM analysis",
    version="0.1.0",
    docs_url="/api/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(kpis.router, prefix="/api/kpis")
app.include_router(anomalies.router, prefix="/api/anomalies")
app.include_router(llm.router, prefix="/api/llm")
app.include_router(reports.router, prefix="/api/reports")
