"""Unit tests for statistical anomaly detectors."""

from __future__ import annotations

import pytest

from kpi_lens.anomaly.statistical import CUSUMDetector, IQRDetector, ZScoreDetector


def test_zscore_detector_spike_returns_anomaly(sample_kpi_df_with_spike):
    det = ZScoreDetector("otif", window_days=30, threshold_sigma=2.5)
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-2:])
    assert len(results) > 0
    assert results[0].kpi_name == "otif"
    assert 0.0 <= results[0].severity <= 1.0


def test_zscore_detector_normal_values_return_empty(sample_kpi_df):
    det = ZScoreDetector("otif")
    det.fit(sample_kpi_df.iloc[:-1])
    # Use the last normal row as current — should not fire
    results = det.detect(sample_kpi_df.iloc[-1:])
    assert results == []


def test_zscore_requires_fit_before_detect(sample_kpi_df):
    det = ZScoreDetector("otif")
    with pytest.raises(RuntimeError, match="fit\\(\\)"):
        det.detect(sample_kpi_df.iloc[-1:])


def test_iqr_detector_outlier_below_fence(sample_kpi_df_with_spike):
    det = IQRDetector("otif", window_days=60)
    det.fit(sample_kpi_df_with_spike.iloc[:-2])
    results = det.detect(sample_kpi_df_with_spike.iloc[-1:])
    assert len(results) > 0
    assert results[0].detector_name == "iqr"


def test_cusum_detects_drift_not_spike(sample_kpi_df):
    """CUSUM should fire on sustained drift even when individual values look normal."""
    df = sample_kpi_df.copy()
    # Introduce a subtle downward drift in the last 10 weeks
    for i in range(10):
        idx = len(df) - 10 + i
        df.loc[idx, "value"] = 93.5 - i * 0.3  # Gradual decline

    det = CUSUMDetector("otif", target_shift_sigma=1.0, decision_interval=4.0)
    det.fit(df.iloc[:-10])
    results = det.detect(df.iloc[-10:])
    # At least one CUSUM alert should fire during the drift window
    assert len(results) > 0


def test_detector_severity_bounded(sample_kpi_df_with_spike):
    """All detectors must return severity in [0, 1]."""
    for detector_class in [ZScoreDetector, IQRDetector, CUSUMDetector]:
        det = detector_class("otif")
        det.fit(sample_kpi_df_with_spike.iloc[:-2])
        results = det.detect(sample_kpi_df_with_spike.iloc[-2:])
        for r in results:
            assert 0.0 <= r.severity <= 1.0, f"{detector_class.__name__} out of bounds"
