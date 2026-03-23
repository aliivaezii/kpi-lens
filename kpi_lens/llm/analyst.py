"""
Supply chain analyst agent — orchestrates anomaly → Claude narrative pipeline.

This module is the bridge between detected anomalies (AnomalyResult) and the
LLM enrichment layer. It is called asynchronously after anomalies are persisted
so that slow API calls never block the detection pipeline.

The analyst uses two modes:
  1. enrich_anomaly(anomaly_id): called automatically after detection
  2. chat(message, history): interactive Q&A from the dashboard chat page
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from kpi_lens.db.repository import KPIRepository
from kpi_lens.kpis.definitions import KPI_BY_NAME
from kpi_lens.llm.client import LLMClient, LLMError
from kpi_lens.llm.context_builder import ContextBuilder
from kpi_lens.llm.prompts import ANOMALY_ANALYSIS, CHAT_SYSTEM, SYSTEM_ANALYST

logger = logging.getLogger(__name__)


class SupplyChainAnalyst:
    """
    Orchestrates LLM analysis for supply chain KPI anomalies.

    Injecting the client and repo as constructor arguments makes this
    trivially testable — pass a mock client, assert on the generated narrative.
    """

    def __init__(
        self,
        client: LLMClient | None = None,
        repo: KPIRepository | None = None,
    ) -> None:
        self._client = client or LLMClient()
        self._repo = repo or KPIRepository()
        self._context = ContextBuilder(self._repo)

    def enrich_anomaly(self, anomaly_id: int) -> None:
        """
        Generate and persist Claude's narrative for a specific anomaly.

        Called asynchronously from the detection pipeline — failures are logged
        but never re-raised, because the anomaly record already exists in the DB.
        """
        try:
            anomaly = self._repo.get_anomaly(anomaly_id)
            if anomaly is None:
                logger.warning("enrich_anomaly called with unknown id=%d", anomaly_id)
                return

            kpi = KPI_BY_NAME.get(anomaly["kpi_name"])
            if kpi is None:
                return

            # Build the trend context for the period surrounding the anomaly
            period_start = date.fromisoformat(str(anomaly["period_start"]))
            trend_df = self._repo.get_kpi_series(
                kpi_name=anomaly["kpi_name"],
                start=period_start - timedelta(weeks=8),
                end=date.fromisoformat(str(anomaly["period_end"])),
            )
            trend_table = self._context.format_trend_table(trend_df)
            correlated = self._context.format_correlated_kpis(
                anomaly["kpi_name"],
                anomaly["period_start"],
                anomaly["period_end"],
            )
            benchmark_distance = kpi.distance_from_benchmark(anomaly["observed_value"])

            prompt = ANOMALY_ANALYSIS.format(
                KPI_DISPLAY_NAME=kpi.display_name,
                KPI_NAME=kpi.name,
                PERIOD_START=anomaly["period_start"],
                PERIOD_END=anomaly["period_end"],
                OBSERVED_VALUE=anomaly["observed_value"],
                UNIT=kpi.unit,
                EXPECTED_LOW=anomaly["expected_low"],
                EXPECTED_HIGH=anomaly["expected_high"],
                SEVERITY=anomaly["severity"],
                DETECTOR_NAME=anomaly["detector_name"],
                HEALTH_STATUS=kpi.health_status(anomaly["observed_value"]),
                BENCHMARK_DISTANCE=benchmark_distance,
                TREND_TABLE=trend_table,
                CORRELATED_KPIS=correlated,
            )

            narrative = self._client.complete(
                system=SYSTEM_ANALYST,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse out recommendations if the model used the structured format
            actions = self._extract_actions(narrative)

            self._repo.update_anomaly_narrative(
                anomaly_id=anomaly_id,
                narrative=narrative,
                actions=json.dumps(actions),
            )
            logger.info("Anomaly %d enriched with LLM narrative", anomaly_id)

        except LLMError as exc:
            # Log and continue — the anomaly is still useful without narrative
            logger.error("LLM enrichment failed for anomaly %d: %s", anomaly_id, exc)

    def chat(
        self,
        message: str,
        history: list[dict[str, str]],
        active_anomaly_count: int = 0,
        overall_health: str = "unknown",
    ) -> str:
        """Interactive Q&A for the dashboard chat page."""
        from datetime import date as _date

        system = CHAT_SYSTEM.format(
            TODAY=_date.today().isoformat(),
            ACTIVE_ANOMALY_COUNT=active_anomaly_count,
            OVERALL_HEALTH=overall_health,
        )
        messages = [*history, {"role": "user", "content": message}]
        return self._client.complete(system=system, messages=messages)

    def _extract_actions(self, narrative: str) -> list[str]:
        """
        Extract numbered recommendations from the narrative text.

        The prompt template asks for a numbered list under '### Recommended Actions'.
        This parser extracts those lines without requiring strict formatting compliance.
        """
        actions: list[str] = []
        in_section = False
        for line in narrative.splitlines():
            if "Recommended Actions" in line:
                in_section = True
                continue
            if in_section and line.startswith(("#", "##")):
                break
            if in_section and line.strip() and line.strip()[0].isdigit():
                actions.append(line.strip().lstrip("0123456789. "))
        return actions[:3]  # Cap at 3 — the prompt asks for exactly 3
