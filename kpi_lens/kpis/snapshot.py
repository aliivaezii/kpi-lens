"""
Snapshot enrichment — adds health_status, benchmark fields, and display metadata
to raw repository output before it leaves the API layer.

The repository returns plain values. This module adds the KPI definition context
(health thresholds, benchmark distances) without coupling the repository to
kpis/definitions.py.
"""

from __future__ import annotations

from typing import Any

from kpi_lens.kpis.definitions import KPI_BY_NAME


def enrich_snapshot(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich a raw repository snapshot with health status and benchmark metadata.
    KPIs absent from KPI_BY_NAME are passed through unchanged.
    """
    result: dict[str, Any] = {}
    for kpi_name, data in raw.items():
        enriched = dict(data)
        kpi_def = KPI_BY_NAME.get(kpi_name)
        if kpi_def and isinstance(data.get("value"), (int, float)):
            value = float(data["value"])
            enriched["health_status"] = kpi_def.health_status(value)
            enriched["benchmark_distance"] = round(
                kpi_def.distance_from_benchmark(value), 2
            )
            enriched["benchmark"] = kpi_def.industry_benchmark
            enriched["display_name"] = kpi_def.display_name
            enriched["direction"] = kpi_def.direction
            enriched["unit"] = kpi_def.unit
        result[kpi_name] = enriched
    return result
