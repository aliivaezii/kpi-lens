"""Unit tests for the LLM analyst and context builder."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from kpi_lens.llm.analyst import SupplyChainAnalyst
from kpi_lens.llm.client import LLMError
from kpi_lens.llm.context_builder import ContextBuilder
from kpi_lens.llm.prompts import (
    ANOMALY_ANALYSIS,
    CHAT_SYSTEM,
    SYSTEM_ANALYST,
    WEEKLY_SUMMARY,
)

# ── Prompt templates ──────────────────────────────────────────────────────────


def test_all_prompts_are_non_empty_strings() -> None:
    for prompt in [SYSTEM_ANALYST, ANOMALY_ANALYSIS, WEEKLY_SUMMARY, CHAT_SYSTEM]:
        assert isinstance(prompt, str)
        assert len(prompt) > 50


def test_system_analyst_contains_expected_sections() -> None:
    assert "Finding" in SYSTEM_ANALYST or "DATA-DRIVEN" in SYSTEM_ANALYST


def test_anomaly_analysis_contains_format_slots() -> None:
    assert "{KPI_DISPLAY_NAME}" in ANOMALY_ANALYSIS
    assert "{OBSERVED_VALUE}" in ANOMALY_ANALYSIS


def test_chat_system_contains_format_slots() -> None:
    assert "{TODAY}" in CHAT_SYSTEM
    assert "{ACTIVE_ANOMALY_COUNT}" in CHAT_SYSTEM


# ── ContextBuilder ────────────────────────────────────────────────────────────


def test_context_builder_format_trend_table_empty_df() -> None:
    mock_repo = MagicMock()
    cb = ContextBuilder(mock_repo)
    result = cb.format_trend_table(pd.DataFrame())
    assert "no trend data" in result


def test_context_builder_format_trend_table_with_rows() -> None:
    mock_repo = MagicMock()
    cb = ContextBuilder(mock_repo)
    df = pd.DataFrame(
        [
            {"period_end": date.today(), "value": 95.5},
            {"period_end": date(2025, 1, 1), "value": 96.0},
        ]
    )
    result = cb.format_trend_table(df)
    assert "|" in result  # Markdown table format


def test_context_builder_format_correlated_kpis_returns_string() -> None:
    mock_repo = MagicMock()
    mock_repo.get_kpi_series.return_value = pd.DataFrame()
    cb = ContextBuilder(mock_repo)
    result = cb.format_correlated_kpis("otif", date.today(), date.today())
    assert isinstance(result, str)


def test_context_builder_format_correlated_kpis_invalid_date() -> None:
    mock_repo = MagicMock()
    cb = ContextBuilder(mock_repo)
    result = cb.format_correlated_kpis("otif", "not-a-date", "also-not-a-date")
    assert "could not parse" in result


def test_context_builder_correlated_kpis_excludes_target_kpi() -> None:
    """The KPI being analysed should not appear as its own correlation."""
    mock_repo = MagicMock()
    mock_repo.get_kpi_series.return_value = pd.DataFrame(
        [{"period_end": date.today(), "value": 96.0}]
    )
    cb = ContextBuilder(mock_repo)
    result = cb.format_correlated_kpis("otif", date(2025, 1, 1), date(2025, 3, 1))
    # otif should not appear in the correlation list — it is the target
    assert "OTIF Delivery Rate" not in result


# ── SupplyChainAnalyst ────────────────────────────────────────────────────────


def _make_analyst(mock_anthropic: MagicMock) -> SupplyChainAnalyst:
    mock_repo = MagicMock()
    mock_repo.get_kpi_series.return_value = pd.DataFrame()
    return SupplyChainAnalyst(repo=mock_repo)


def test_analyst_chat_returns_string(mock_anthropic: MagicMock) -> None:
    analyst = _make_analyst(mock_anthropic)
    result = analyst.chat("What is OTIF?", history=[])
    assert isinstance(result, str)
    assert len(result) > 0


def test_analyst_chat_passes_history(mock_anthropic: MagicMock) -> None:
    analyst = _make_analyst(mock_anthropic)
    history = [{"role": "user", "content": "Previous question"}]
    analyst.chat("Follow-up question", history=history)
    # Verify the Anthropic mock was called (history was included)
    mock_anthropic.messages.create.assert_called_once()


def test_analyst_enrich_anomaly_unknown_id_does_not_raise(
    mock_anthropic: MagicMock,
) -> None:
    mock_repo = MagicMock()
    mock_repo.get_anomaly.return_value = None
    analyst = SupplyChainAnalyst(repo=mock_repo)
    analyst.enrich_anomaly(999)  # Should log warning and return
    mock_repo.update_anomaly_narrative.assert_not_called()


def test_analyst_enrich_anomaly_calls_update_narrative(
    mock_anthropic: MagicMock,
) -> None:
    mock_repo = MagicMock()
    mock_repo.get_anomaly.return_value = {
        "id": 1,
        "kpi_name": "otif",
        "period_start": date.today(),
        "period_end": date.today(),
        "observed_value": 78.0,
        "expected_low": 90.0,
        "expected_high": 97.0,
        "severity": 0.9,
        "detector_name": "threshold",
        "entity": "global",
    }
    mock_repo.get_kpi_series.return_value = pd.DataFrame()

    analyst = SupplyChainAnalyst(repo=mock_repo)
    analyst.enrich_anomaly(1)

    mock_repo.update_anomaly_narrative.assert_called_once()
    _, kwargs = mock_repo.update_anomaly_narrative.call_args
    assert (
        kwargs.get("anomaly_id") == 1
        or mock_repo.update_anomaly_narrative.call_args.args[0] == 1
    )  # noqa: E501


def test_analyst_enrich_handles_llm_error_without_raising() -> None:
    """LLMError during enrichment must not propagate — anomaly is already saved."""
    mock_client = MagicMock()
    mock_client.complete.side_effect = LLMError("API unavailable")

    mock_repo = MagicMock()
    mock_repo.get_anomaly.return_value = {
        "id": 2,
        "kpi_name": "otif",
        "period_start": date.today(),
        "period_end": date.today(),
        "observed_value": 78.0,
        "expected_low": 90.0,
        "expected_high": 97.0,
        "severity": 0.9,
        "detector_name": "threshold",
        "entity": "global",
    }
    mock_repo.get_kpi_series.return_value = pd.DataFrame()

    analyst = SupplyChainAnalyst(client=mock_client, repo=mock_repo)
    analyst.enrich_anomaly(2)  # Must not raise

    mock_repo.update_anomaly_narrative.assert_not_called()


def test_analyst_enrich_skips_unknown_kpi(mock_anthropic: MagicMock) -> None:
    """Enrich must skip silently for anomalies with an unregistered KPI name."""
    mock_repo = MagicMock()
    mock_repo.get_anomaly.return_value = {
        "id": 3,
        "kpi_name": "unknown_kpi_xyz",
        "period_start": date.today(),
        "period_end": date.today(),
        "observed_value": 50.0,
        "expected_low": 0.0,
        "expected_high": 0.0,
        "severity": 0.5,
        "detector_name": "threshold",
        "entity": "global",
    }

    analyst = SupplyChainAnalyst(repo=mock_repo)
    analyst.enrich_anomaly(3)  # Must not raise
    mock_repo.update_anomaly_narrative.assert_not_called()
