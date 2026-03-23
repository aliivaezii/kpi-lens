"""Unit tests for the ensemble anomaly detector."""

from __future__ import annotations

import pandas as pd
import pytest

from kpi_lens.anomaly.ensemble import EnsembleDetector


def test_ensemble_raises_on_unknown_kpi() -> None:
    with pytest.raises(ValueError, match="Unknown KPI"):
        EnsembleDetector("not_a_real_kpi")


def test_ensemble_fit_and_detect_return_types(
    sample_kpi_df_with_spike: pd.DataFrame,
) -> None:
    det = EnsembleDetector("otif")
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-2:])
    assert isinstance(results, list)


def test_ensemble_fires_on_red_value(sample_kpi_df_with_spike: pd.DataFrame) -> None:
    """
    78% OTIF triggers the threshold detector (always-on, no history required).
    The ensemble must return exactly one fused result.
    """
    det = EnsembleDetector("otif")
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-1:])
    assert len(results) == 1
    assert results[0].severity > 0.0
    assert results[0].kpi_name == "otif"


def test_ensemble_result_name_contains_ensemble(
    sample_kpi_df_with_spike: pd.DataFrame,
) -> None:
    det = EnsembleDetector("otif")
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-1:])
    assert len(results) == 1
    assert "ensemble" in results[0].detector_name


def test_ensemble_severity_bounded(sample_kpi_df_with_spike: pd.DataFrame) -> None:
    det = EnsembleDetector("otif")
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-1:])
    for r in results:
        assert 0.0 <= r.severity <= 1.0


def test_ensemble_returns_at_most_one_result(
    sample_kpi_df_with_spike: pd.DataFrame,
) -> None:
    """Ensemble must fuse all sub-detector signals into a single AnomalyResult."""
    det = EnsembleDetector("otif")
    det.fit(sample_kpi_df_with_spike)
    results = det.detect(sample_kpi_df_with_spike.iloc[-1:])
    assert len(results) <= 1


def test_ensemble_context_has_detector_count(
    sample_kpi_df_with_spike: pd.DataFrame,
) -> None:
    det = EnsembleDetector("otif")
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-1:])
    if results:
        assert "detector_count" in results[0].context
        assert int(results[0].context["detector_count"]) >= 1


def test_ensemble_works_for_lower_is_better_kpi(
    sample_kpi_df: pd.DataFrame,
) -> None:
    """Ensemble must initialise and run without error for a lower_is_better KPI."""
    from datetime import date, timedelta

    today = date.today()
    df = pd.DataFrame(
        [
            {
                "period_start": today - timedelta(weeks=i + 1),
                "period_end": today - timedelta(weeks=i),
                "value": float(40 + i * 0.3),
                "entity": "global",
            }
            for i in range(30)
        ]
    )
    # Inject a red-threshold breach (DIO > 60)
    df.loc[0, "value"] = 75.0
    det = EnsembleDetector("dio")
    det.fit(df.iloc[1:])
    results = det.detect(df.iloc[:1])
    assert isinstance(results, list)
