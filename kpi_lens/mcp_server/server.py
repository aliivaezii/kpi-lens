"""
KPI-Lens MCP Server — gives Claude structured, read-only access to supply chain KPIs.

Run standalone:
    python -m kpi_lens.mcp_server.server

Or via Docker:
    docker compose --profile tools up mcp

The server uses the `mcp` (FastMCP) library to expose tools that Claude calls
during supply chain analysis sessions. All tools are read-only — the only
write-side tool (report_trigger) enqueues a job rather than executing it.

Tool registration order matches the recommended context window loading order:
  1. get_kpi_schema   (resource) — Claude reads definitions first
  2. get_kpi_snapshot            — current state of all 8 KPIs
  3. get_recent_anomalies        — what needs investigation
  4. get_kpi_time_series         — drill into a specific KPI
  5. compare_to_benchmark        — frame severity against industry
  6. get_supplier_breakdown      — root cause: which supplier?
  7. trigger_report              — act: generate an executive report
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from mcp.server.fastmcp import FastMCP

from kpi_lens.db.repository import KPIRepository
from kpi_lens.kpis.definitions import ALL_KPIS, KPI_BY_NAME

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "kpi-lens",
    instructions=(
        "You are a supply chain intelligence analyst with access to live KPI data. "
        "Always call get_kpi_schema first to understand thresholds and benchmarks. "
        "Then call get_kpi_snapshot to see the current state "
        "before investigating anomalies."
    ),
)

# Repository is instantiated once at server startup — connection is reused per tool call
_repo = KPIRepository()


# ── Resources (loaded into Claude's context at session start) ─────────────────


@mcp.resource("kpi-lens://schema/kpis")
def get_kpi_schema() -> str:
    """
    KPI definitions: names, units, thresholds, and industry benchmarks.
    Read this first to understand what 'good' looks like for each KPI.
    """
    schema = {
        kpi.name: {
            "display_name": kpi.display_name,
            "unit": kpi.unit,
            "direction": kpi.direction,
            "thresholds": {
                "green": kpi.green_threshold,
                "yellow": kpi.yellow_threshold,
                "red": kpi.red_threshold,
            },
            "industry_benchmark": kpi.industry_benchmark,
            "description": kpi.description,
        }
        for kpi in ALL_KPIS
    }
    return json.dumps(schema, indent=2)


# ── Tools ─────────────────────────────────────────────────────────────────────


@mcp.tool()
def get_kpi_snapshot(reference_date: str | None = None) -> dict[str, Any]:
    """
    Current value for all 8 KPIs as of reference_date (default: today).
    Returns health status (green/yellow/red), MoM delta, and benchmark distance.
    Use this as your starting point before investigating any specific KPI.

    Args:
        reference_date: ISO-8601 date string, e.g. '2024-11-01'. Defaults to today.
    """
    ref = date.fromisoformat(reference_date) if reference_date else date.today()
    snapshot = _repo.get_latest_snapshot(as_of=ref)
    return snapshot


@mcp.tool()
def get_kpi_time_series(
    kpi_name: str,
    start_date: str,
    end_date: str,
    entity: str = "global",
    granularity: str = "weekly",
) -> dict[str, Any]:
    """
    Historical values for a single KPI over a date range.
    Use to identify trends, seasonality, and the build-up before an anomaly.

    Args:
        kpi_name: One of: otif, inventory_turn, dio, supplier_dppm, dfa,
                  fill_rate, ltv, po_cycle_time
        start_date: ISO-8601, e.g. '2024-01-01'
        end_date: ISO-8601, e.g. '2024-12-31'
        entity: 'global', or a supplier/plant/SKU identifier
        granularity: 'daily', 'weekly', or 'monthly'
    """
    if kpi_name not in KPI_BY_NAME:
        return {"error": f"Unknown KPI: {kpi_name!r}. Valid: {list(KPI_BY_NAME)}"}

    series = _repo.get_kpi_series(
        kpi_name=kpi_name,
        start=date.fromisoformat(start_date),
        end=date.fromisoformat(end_date),
        entity=entity,
    )
    kpi = KPI_BY_NAME[kpi_name]
    return {
        "kpi_name": kpi_name,
        "display_name": kpi.display_name,
        "unit": kpi.unit,
        "direction": kpi.direction,
        "benchmark": kpi.industry_benchmark,
        "data_points": len(series),
        "series": series.to_dict(orient="records"),
    }


@mcp.tool()
def get_recent_anomalies(
    days_back: int = 30,
    severity_floor: float = 0.3,
    kpi_filter: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Anomaly events from the last N days, sorted by severity descending.
    Start here to understand what needs investigation right now.

    Args:
        days_back: Look back window in calendar days (default 30)
        severity_floor: Minimum severity 0.0–1.0 (default 0.3 = moderate)
        kpi_filter: Limit to specific KPIs, e.g. ['otif', 'supplier_dppm']
    """
    anomalies = _repo.get_recent_anomalies(
        days_back=days_back,
        severity_floor=severity_floor,
        kpi_filter=kpi_filter,
    )
    return anomalies


@mcp.tool()
def compare_to_benchmark(kpi_name: str, industry: str = "automotive") -> dict[str, Any]:
    """
    Compare the current KPI value to industry percentiles (P25/P50/P75/P90).
    Frames whether an anomaly is 'below industry median' vs 'historically unusual'.

    Args:
        kpi_name: KPI identifier
        industry: 'automotive' or 'general_manufacturing'
    """
    if kpi_name not in KPI_BY_NAME:
        return {"error": f"Unknown KPI: {kpi_name!r}"}
    kpi = KPI_BY_NAME[kpi_name]
    current = _repo.get_latest_value(kpi_name)
    benchmarks = _repo.get_benchmarks(kpi_name, industry)
    return {
        "kpi_name": kpi_name,
        "current_value": current,
        "unit": kpi.unit,
        "internal_status": kpi.health_status(current) if current else "unknown",
        "benchmarks": benchmarks,
        "distance_from_median_pct": kpi.distance_from_benchmark(current)
        if current
        else None,
    }


@mcp.tool()
def get_supplier_breakdown(
    kpi_name: str,
    period_start: str,
    period_end: str,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """
    Per-supplier values for supplier-facing KPIs over a period.
    Use to determine if an anomaly is systemic (all suppliers) or concentrated.

    Args:
        kpi_name: One of: supplier_dppm, otif, ltv, po_cycle_time
        period_start: ISO-8601 date
        period_end: ISO-8601 date
        top_n: Return the N worst-performing suppliers
    """
    supplier_kpis = {"supplier_dppm", "otif", "ltv", "po_cycle_time"}
    if kpi_name not in supplier_kpis:
        return [{"error": f"{kpi_name} does not have supplier-level breakdown"}]

    return _repo.get_entity_breakdown(
        kpi_name=kpi_name,
        start=date.fromisoformat(period_start),
        end=date.fromisoformat(period_end),
        top_n=top_n,
        entity_prefix="supplier:",
    )


@mcp.tool()
def trigger_report(
    anomaly_ids: list[int],
    recipient_emails: list[str],
    include_recommendations: bool = True,
) -> dict[str, Any]:
    """
    Enqueue generation and email delivery of a focused anomaly report.
    The report is generated asynchronously — this call returns immediately
    with a job_id that can be used to check status.

    Args:
        anomaly_ids: IDs of specific anomalies to include in the report
        recipient_emails: List of email addresses to send the PDF to
        include_recommendations: Whether to include Claude's action recommendations
    """
    job_id = _repo.enqueue_report(
        anomaly_ids=anomaly_ids,
        recipients=recipient_emails,
        include_recommendations=include_recommendations,
        triggered_by="mcp_tool",
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "message": f"Report queued for {len(anomaly_ids)} anomalies. "
        f"Will be delivered to {len(recipient_emails)} recipients.",
    }


if __name__ == "__main__":
    mcp.run()
