"""Unit tests for the rule-based threshold detector."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from kpi_lens.anomaly.threshold import ThresholdDetector


def _make_df(value: float, kpi: str = "otif") -> pd.DataFrame:
    today = date.today()
    return pd.DataFrame(
        [
            {
                "period_start": today - timedelta(days=7),
                "period_end": today,
                "value": value,
                "entity": "global",
            }
        ]
    )


def test_threshold_fires_with_severity_one_on_red_otif() -> None:
    """78% OTIF is below the red threshold (85%) — must fire with severity 1.0."""
    det = ThresholdDetector("otif")
    det.fit(_make_df(96.0))  # fit is a no-op; data is irrelevant
    results = det.detect(_make_df(78.0))
    assert len(results) == 1
    assert results[0].severity == 1.0
    assert results[0].kpi_name == "otif"
    assert results[0].detector_name == "threshold"


def test_threshold_no_fire_on_green_otif() -> None:
    """96% OTIF is well within green — no anomaly expected."""
    det = ThresholdDetector("otif")
    det.fit(_make_df(96.0))
    results = det.detect(_make_df(96.0))
    assert results == []


def test_threshold_no_fire_on_yellow_otif() -> None:
    """92% OTIF is yellow (between green=95 and red=85).

    Threshold detector only fires on red; yellow must be a no-op.
    """
    det = ThresholdDetector("otif")
    det.fit(_make_df(96.0))
    results = det.detect(_make_df(92.0))
    assert results == []


def test_threshold_fires_for_lower_is_better_kpi_above_red() -> None:
    """DIO of 70 days exceeds the red threshold (60) — must fire."""
    det = ThresholdDetector("dio")
    det.fit(_make_df(35.0, "dio"))
    results = det.detect(_make_df(70.0, "dio"))
    assert len(results) == 1
    assert results[0].severity == 1.0


def test_threshold_no_fire_for_lower_is_better_kpi_in_green() -> None:
    """DIO of 25 days is comfortably green — no anomaly."""
    det = ThresholdDetector("dio")
    det.fit(_make_df(35.0, "dio"))
    results = det.detect(_make_df(25.0, "dio"))
    assert results == []


def test_threshold_requires_fit_before_detect(sample_kpi_df: pd.DataFrame) -> None:
    det = ThresholdDetector("otif")
    with pytest.raises(RuntimeError, match="fit\\(\\)"):
        det.detect(sample_kpi_df.iloc[-1:])


def test_threshold_expected_range_set_correctly() -> None:
    """expected_range on the result should reflect the KPI's green/yellow bounds."""
    det = ThresholdDetector("otif")
    det.fit(_make_df(96.0))
    results = det.detect(_make_df(78.0))
    assert len(results) == 1
    low, high = results[0].expected_range
    # For higher_is_better: (yellow, green)
    assert low < high


def test_threshold_context_contains_threshold_type() -> None:
    det = ThresholdDetector("otif")
    det.fit(_make_df(96.0))
    results = det.detect(_make_df(78.0))
    assert results[0].context.get("threshold_type") == "red"
