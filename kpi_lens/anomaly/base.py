"""
Abstract base class and shared types for the anomaly detection pipeline.

All detector implementations must subclass AnomalyDetector and return
AnomalyResult objects. The ensemble in ensemble.py is the only consumer
of detector outputs — individual detectors are never called directly by
the API, dashboard, or reporting layers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


@dataclass
class AnomalyResult:
    """
    A single anomaly signal from one detector for one KPI time window.

    severity is normalized to [0, 1] by the detector before returning.
    The ensemble re-weights and combines multiple AnomalyResult objects
    into a single consolidated result per KPI window.
    """

    kpi_name: str
    detected_at: datetime
    period_start: datetime
    period_end: datetime
    observed_value: float
    # (low, high) bounds define the "normal" range the detector computed
    expected_range: tuple[float, float]
    # Normalized 0.0–1.0: 0 = barely anomalous, 1 = extreme outlier
    severity: float
    detector_name: str
    entity: str = "global"
    # Detector-specific metadata for debugging and audit (not shown in UI)
    context: dict[str, float | str | int] = field(default_factory=dict)

    @property
    def expected_low(self) -> float:
        return self.expected_range[0]

    @property
    def expected_high(self) -> float:
        return self.expected_range[1]

    def is_above_floor(self, floor: float) -> bool:
        return self.severity >= floor


class AnomalyDetector(ABC):
    """
    Interface contract for all anomaly detectors.

    Detectors are stateful: fit() trains/calibrates the model on historical data,
    detect() applies the model to a current observation window.

    fit() must be called before detect(). Calling detect() on an unfitted
    detector raises RuntimeError — never return empty results silently.

    DataFrame schema expected by both methods:
        period_start  : datetime
        period_end    : datetime
        value         : float
        entity        : str  (optional, default 'global')
    """

    def __init__(self, kpi_name: str) -> None:
        self._kpi_name = kpi_name
        self._is_fitted = False

    @property
    def name(self) -> str:
        """Unique identifier used in AnomalyResult.detector_name and DB records."""
        return self.__class__.__name__.lower().replace("detector", "")

    @abstractmethod
    def fit(self, historical: pd.DataFrame) -> None:
        """
        Calibrate the detector on historical KPI data.

        After this call, self._is_fitted must be True.
        historical must contain at least min_history_days rows — callers
        are responsible for checking before calling fit().
        """
        ...

    @abstractmethod
    def detect(self, current: pd.DataFrame) -> list[AnomalyResult]:
        """
        Apply the fitted model to the current observation window.

        Returns a (possibly empty) list of AnomalyResult objects.
        Each result's severity is normalized to [0, 1] by this method.
        """
        ...

    def _require_fitted(self) -> None:
        if not self._is_fitted:
            raise RuntimeError(
                f"{self.__class__.__name__}.detect() called before fit(). "
                "Call fit(historical_df) first."
            )
