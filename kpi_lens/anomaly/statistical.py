"""
Statistical anomaly detectors: Z-score, IQR, and CUSUM.

Each detector is independent and stateless between fit/detect cycles.
The ensemble in ensemble.py combines their signals — do not call these
directly from outside the anomaly/ package.

Design rationale for three detectors rather than one:
- Z-score catches sudden point spikes (e.g. a DPPM reading 5× the rolling mean)
- IQR catches distribution shifts that occur gradually (robust to outliers in fit)
- CUSUM catches sustained directional drift that neither Z-score nor IQR detect
  until the drift has accumulated enough to shift the rolling statistics
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from kpi_lens.anomaly.base import AnomalyDetector, AnomalyResult


class ZScoreDetector(AnomalyDetector):
    """
    Flag observations more than `threshold_sigma` standard deviations
    from the rolling mean.

    Window defaults to 30 days — short enough to adapt to level shifts
    while long enough to smooth weekly noise.
    """

    def __init__(
        self,
        kpi_name: str,
        window_days: int = 30,
        threshold_sigma: float = 2.5,
    ) -> None:
        super().__init__(kpi_name)
        self._window = window_days
        self._threshold = threshold_sigma
        self._rolling_mean: float = 0.0
        self._rolling_std: float = 1.0

    def fit(self, historical: pd.DataFrame) -> None:
        values = historical["value"].astype(float)
        self._rolling_mean = float(values.tail(self._window).mean())
        self._rolling_std = float(values.tail(self._window).std())
        # Avoid division by zero on perfectly constant series
        if self._rolling_std < 1e-9:
            self._rolling_std = 1e-9
        self._is_fitted = True

    def detect(self, current: pd.DataFrame) -> list[AnomalyResult]:
        self._require_fitted()
        results = []
        for _, row in current.iterrows():
            value = float(row["value"])
            z = (value - self._rolling_mean) / self._rolling_std
            if abs(z) > self._threshold:
                # Normalize severity: maps z=threshold → 0.3, z=3×threshold → 1.0
                severity = min(1.0, (abs(z) - self._threshold) / (2 * self._threshold))
                results.append(
                    AnomalyResult(
                        kpi_name=self._kpi_name,
                        detected_at=datetime.utcnow(),
                        period_start=row["period_start"],
                        period_end=row["period_end"],
                        observed_value=value,
                        expected_range=(
                            self._rolling_mean - self._threshold * self._rolling_std,
                            self._rolling_mean + self._threshold * self._rolling_std,
                        ),
                        severity=severity,
                        detector_name=self.name,
                        entity=str(row.get("entity", "global")),
                        context={"z_score": round(z, 3), "window_days": self._window},
                    )
                )
        return results


class IQRDetector(AnomalyDetector):
    """
    Flag observations outside the Tukey fence (Q1 - k×IQR, Q3 + k×IQR).

    Uses a 90-day window by default — longer than Z-score because IQR is
    designed to capture gradual distribution shifts and is robust to the
    very outliers it is trying to detect (unlike Z-score whose mean/std
    are distorted by the outliers themselves).
    """

    def __init__(
        self,
        kpi_name: str,
        window_days: int = 90,
        fence_multiplier: float = 1.5,
    ) -> None:
        super().__init__(kpi_name)
        self._window = window_days
        self._k = fence_multiplier
        self._lower_fence: float = 0.0
        self._upper_fence: float = 0.0
        self._q1: float = 0.0
        self._q3: float = 0.0

    def fit(self, historical: pd.DataFrame) -> None:
        values = historical["value"].astype(float).tail(self._window)
        self._q1 = float(np.percentile(values, 25))
        self._q3 = float(np.percentile(values, 75))
        iqr = self._q3 - self._q1
        self._lower_fence = self._q1 - self._k * iqr
        self._upper_fence = self._q3 + self._k * iqr
        self._is_fitted = True

    def detect(self, current: pd.DataFrame) -> list[AnomalyResult]:
        self._require_fitted()
        results = []
        iqr = self._q3 - self._q1 or 1e-9
        for _, row in current.iterrows():
            value = float(row["value"])
            if value < self._lower_fence or value > self._upper_fence:
                distance = max(
                    self._lower_fence - value, value - self._upper_fence, 0.0
                )
                severity = min(1.0, distance / (self._k * iqr))
                results.append(
                    AnomalyResult(
                        kpi_name=self._kpi_name,
                        detected_at=datetime.utcnow(),
                        period_start=row["period_start"],
                        period_end=row["period_end"],
                        observed_value=value,
                        expected_range=(self._lower_fence, self._upper_fence),
                        severity=severity,
                        detector_name=self.name,
                        entity=str(row.get("entity", "global")),
                        context={
                            "q1": round(self._q1, 3),
                            "q3": round(self._q3, 3),
                            "fence_multiplier": self._k,
                        },
                    )
                )
        return results


class CUSUMDetector(AnomalyDetector):
    """
    Barnard two-sided CUSUM for detecting sustained directional drift.

    Z-score and IQR detect point anomalies. CUSUM is designed for the case
    where each individual reading is within normal bounds but the cumulative
    sum of deviations reveals a systematic upward or downward trend —
    the classic early-warning pattern for supplier lead-time creep or
    gradual inventory accumulation.

    target_shift_sigma: the minimum shift (in σ units) worth detecting
    decision_interval: CUSUM threshold before raising a flag (h parameter)
    """

    def __init__(
        self,
        kpi_name: str,
        target_shift_sigma: float = 1.0,
        decision_interval: float = 4.0,
    ) -> None:
        super().__init__(kpi_name)
        self._target_shift = target_shift_sigma
        self._h = decision_interval
        self._mu: float = 0.0
        self._sigma: float = 1.0

    def fit(self, historical: pd.DataFrame) -> None:
        values = historical["value"].astype(float)
        self._mu = float(values.mean())
        self._sigma = float(values.std()) or 1e-9
        self._is_fitted = True

    def detect(self, current: pd.DataFrame) -> list[AnomalyResult]:
        self._require_fitted()
        values = current["value"].astype(float).tolist()
        k = self._target_shift * self._sigma / 2
        cusum_pos, cusum_neg = 0.0, 0.0
        results = []

        for i, (_, row) in enumerate(current.iterrows()):
            v = values[i]
            cusum_pos = max(0.0, cusum_pos + (v - self._mu) / self._sigma - k)
            cusum_neg = max(0.0, cusum_neg - (v - self._mu) / self._sigma - k)
            if cusum_pos > self._h or cusum_neg > self._h:
                cusum_magnitude = max(cusum_pos, cusum_neg)
                severity = min(1.0, cusum_magnitude / (2 * self._h))
                results.append(
                    AnomalyResult(
                        kpi_name=self._kpi_name,
                        detected_at=datetime.utcnow(),
                        period_start=row["period_start"],
                        period_end=row["period_end"],
                        observed_value=float(v),
                        expected_range=(
                            self._mu - self._h * self._sigma,
                            self._mu + self._h * self._sigma,
                        ),
                        severity=severity,
                        detector_name=self.name,
                        entity=str(row.get("entity", "global")),
                        context={
                            "cusum_pos": round(cusum_pos, 3),
                            "cusum_neg": round(cusum_neg, 3),
                            "decision_interval": self._h,
                        },
                    )
                )
        return results
