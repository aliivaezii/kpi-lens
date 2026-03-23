"""Unit tests for the Isolation Forest ML anomaly detector."""

from __future__ import annotations

import pandas as pd
import pytest

from kpi_lens.anomaly.ml import IsolationForestDetector


def test_isolation_forest_is_not_fitted_initially() -> None:
    det = IsolationForestDetector("otif")
    assert not det._is_fitted


def test_isolation_forest_is_fitted_after_fit(sample_kpi_df: pd.DataFrame) -> None:
    det = IsolationForestDetector("otif", n_estimators=10)
    det.fit(sample_kpi_df)
    assert det._is_fitted


def test_isolation_forest_requires_fit_before_detect(
    sample_kpi_df: pd.DataFrame,
) -> None:
    det = IsolationForestDetector("otif")
    with pytest.raises(RuntimeError, match="fit\\(\\)"):
        det.detect(sample_kpi_df.iloc[-1:])


def test_isolation_forest_detect_returns_list(sample_kpi_df: pd.DataFrame) -> None:
    det = IsolationForestDetector("otif", n_estimators=10)
    det.fit(sample_kpi_df.iloc[:-5])
    results = det.detect(sample_kpi_df.iloc[-5:])
    assert isinstance(results, list)


def test_isolation_forest_severity_bounded(
    sample_kpi_df_with_spike: pd.DataFrame,
) -> None:
    """Every result must have severity in [0, 1]."""
    det = IsolationForestDetector("otif", contamination=0.1, n_estimators=10)
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-2:])
    for r in results:
        assert 0.0 <= r.severity <= 1.0


def test_isolation_forest_detector_name(sample_kpi_df: pd.DataFrame) -> None:
    det = IsolationForestDetector("otif", n_estimators=10)
    det.fit(sample_kpi_df)
    results = det.detect(sample_kpi_df.iloc[-5:])
    for r in results:
        assert r.detector_name == "isolationforest"


def test_isolation_forest_kpi_name_on_result(
    sample_kpi_df_with_spike: pd.DataFrame,
) -> None:
    det = IsolationForestDetector("supplier_dppm", contamination=0.15, n_estimators=10)
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-2:])
    for r in results:
        assert r.kpi_name == "supplier_dppm"


def test_isolation_forest_context_has_if_score(
    sample_kpi_df_with_spike: pd.DataFrame,
) -> None:
    det = IsolationForestDetector("otif", contamination=0.15, n_estimators=10)
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-2:])
    for r in results:
        assert "if_score" in r.context


def test_isolation_forest_expected_range_is_zero_tuple(
    sample_kpi_df_with_spike: pd.DataFrame,
) -> None:
    """
    IsolationForest does not produce explicit normal-range bounds —
    expected_range is always (0.0, 0.0) per the detector contract.
    """
    det = IsolationForestDetector("otif", contamination=0.15, n_estimators=10)
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-2:])
    for r in results:
        assert r.expected_range == (0.0, 0.0)
