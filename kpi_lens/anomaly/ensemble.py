"""
Ensemble anomaly detector — combines signals from all sub-detectors.

This is the only entry point for anomaly detection used by the rest of
the application. The pipeline (threshold → statistical → ml) runs here.
Individual detectors are an implementation detail of this module.

Weight configuration lives in config/anomaly.yaml so thresholds can be
tuned without code changes. The ensemble applies weighted voting and
emits a single AnomalyResult per KPI per time window.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from kpi_lens.anomaly.base import AnomalyDetector, AnomalyResult
from kpi_lens.anomaly.statistical import CUSUMDetector, IQRDetector, ZScoreDetector
from kpi_lens.anomaly.threshold import ThresholdDetector
from kpi_lens.kpis.definitions import KPI_BY_NAME

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "anomaly.yaml"


def _load_config() -> dict[str, Any]:
    with _CONFIG_PATH.open() as f:
        result: dict[str, Any] = yaml.safe_load(f)["detection"]
        return result


class EnsembleDetector:
    """
    Runs the full detector pipeline for a single KPI and fuses signals.

    Usage:
        detector = EnsembleDetector("otif")
        detector.fit(historical_df)
        anomalies = detector.detect(current_df)
    """

    def __init__(self, kpi_name: str) -> None:
        if kpi_name not in KPI_BY_NAME:
            raise ValueError(f"Unknown KPI: {kpi_name!r}. Valid: {list(KPI_BY_NAME)}")
        self._kpi_name = kpi_name
        self._config = _load_config()
        self._detectors: list[AnomalyDetector] = self._build_detectors()
        self._weights = self._config["weights"]

    def _build_detectors(self) -> list[AnomalyDetector]:
        stat = self._config["statistical"]
        return [
            ThresholdDetector(self._kpi_name),
            ZScoreDetector(
                self._kpi_name,
                window_days=stat["zscore"]["window_days"],
                threshold_sigma=stat["zscore"]["threshold_sigma"],
            ),
            IQRDetector(
                self._kpi_name,
                window_days=stat["iqr"]["window_days"],
                fence_multiplier=stat["iqr"]["fence_multiplier"],
            ),
            CUSUMDetector(
                self._kpi_name,
                target_shift_sigma=stat["cusum"]["target_shift_sigma"],
                decision_interval=stat["cusum"]["decision_interval"],
            ),
        ]

    def fit(self, historical: pd.DataFrame) -> None:
        n_days = len(historical)
        min_days = self._config["min_history_days"]
        if n_days < min_days:
            logger.warning(
                "Only %d days of history for %s; minimum is %d. "
                "Only ThresholdDetector will run.",
                n_days,
                self._kpi_name,
                min_days,
            )
        for detector in self._detectors:
            try:
                detector.fit(historical)
            except Exception:
                logger.exception(
                    "fit() failed for %s on %s", detector.name, self._kpi_name
                )

    def detect(self, current: pd.DataFrame) -> list[AnomalyResult]:
        """
        Run all fitted detectors and return the fused anomaly result.

        Returns an empty list if no detector fires above the severity floor.
        Returns a list with one AnomalyResult (the ensemble-weighted result)
        if any detector fires.
        """
        floor = self._config["severity_floor"]
        all_results: list[AnomalyResult] = []

        for detector in self._detectors:
            try:
                results = detector.detect(current)
                all_results.extend(r for r in results if r.is_above_floor(floor))
            except Exception:
                logger.exception("detect() failed for %s", detector.name)

        if not all_results:
            return []

        return [self._fuse(all_results)]

    def _fuse(self, results: list[AnomalyResult]) -> AnomalyResult:
        """Weighted-average fusion of multiple detector signals into one result."""
        weight_map = {
            "threshold": self._weights.get("threshold", 1.0),
            "zscore": self._weights.get("zscore", 0.35),
            "iqr": self._weights.get("iqr", 0.30),
            "cusum": self._weights.get("cusum", 0.35),
            "isolationforest": self._weights.get("isolation_forest", 0.80),
        }
        weighted_severity = 0.0
        total_weight = 0.0
        for r in results:
            w = weight_map.get(r.detector_name, 0.5)
            weighted_severity += r.severity * w
            total_weight += w

        fused_severity = (
            min(1.0, weighted_severity / total_weight) if total_weight else 0.0
        )

        # Use the result with highest individual severity as the template
        primary = max(results, key=lambda r: r.severity)
        detector_names = ",".join(sorted({r.detector_name for r in results}))

        return AnomalyResult(
            kpi_name=primary.kpi_name,
            detected_at=primary.detected_at,
            period_start=primary.period_start,
            period_end=primary.period_end,
            observed_value=primary.observed_value,
            expected_range=primary.expected_range,
            severity=fused_severity,
            detector_name=f"ensemble({detector_names})",
            entity=primary.entity,
            context={"detector_count": len(results), "detectors_fired": detector_names},
        )
