"""
Context builder — formats repository data into LLM-ready text tables.

Keeps all string-formatting logic out of analyst.py so prompt templates
stay clean and context assembly is independently testable.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from kpi_lens.db.repository import KPIRepository


class ContextBuilder:
    """Formats KPI data from the repository into text for LLM prompts."""

    def __init__(self, repo: KPIRepository) -> None:
        self._repo = repo

    def format_trend_table(self, df: pd.DataFrame) -> str:
        """Return a markdown-style table of period → value rows."""
        if df.empty:
            return "(no trend data available)"
        lines = ["| Period End   | Value |", "|---|---|"]
        for _, row in df.iterrows():
            lines.append(f"| {row['period_end']} | {row['value']:.2f} |")
        return "\n".join(lines)

    def format_correlated_kpis(
        self,
        kpi_name: str,
        period_start: date | str,
        period_end: date | str,
    ) -> str:
        """
        Return a text summary of other KPIs during the same period.

        Correlations help Claude hypothesize root causes — e.g. if OTIF drops
        while Supplier DPPM spikes, the supplier is the likely root cause.
        """
        try:
            start = date.fromisoformat(str(period_start))
            end = date.fromisoformat(str(period_end))
        except ValueError:
            return "(could not parse period dates)"

        from kpi_lens.kpis.definitions import KPI_BY_NAME

        lines: list[str] = []
        for name, kpi in KPI_BY_NAME.items():
            if name == kpi_name:
                continue
            series = self._repo.get_kpi_series(name, start, end)
            if series.empty:
                continue
            latest = float(series["value"].iloc[-1])
            status = kpi.health_status(latest)
            lines.append(f"- {kpi.display_name}: {latest:.2f} {kpi.unit} [{status}]")

        return "\n".join(lines) if lines else "(no correlated KPI data)"
