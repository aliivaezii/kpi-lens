"""
ML-based anomaly detector: Isolation Forest.

Activated only when ≥60 days of history are available (configured in
config/anomaly.yaml: ml_activation_days). Retrained monthly.

Isolation Forest is chosen over One-Class SVM because it scales to the
feature set used here (6 lag features) without hyperparameter sensitivity,
and its contamination parameter maps cleanly to an expected anomaly rate.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from kpi_lens.anomaly.base import AnomalyDetector, AnomalyResult

logger = logging.getLogger(__name__)


class IsolationForestDetector(AnomalyDetector):
    """
    Multivariate anomaly detection using 6 engineered time-series features.

    Features per observation:
      1. raw value
      2. 7-day lag
      3. 14-day lag
      4. rolling 7-day mean
      5. rolling 30-day std
      6. value minus rolling 7-day mean (deviation from local trend)

    Using lag features rather than just the raw value lets the forest detect
    "normal value, abnormal context" anomalies — e.g. OTIF of 93% is fine
    in a historically volatile period but anomalous if it's been 98% for 3 months.
    """

    def __init__(
        self,
        kpi_name: str,
        contamination: float = 0.05,
        n_estimators: int = 200,
        model_dir: Path | None = None,
    ) -> None:
        super().__init__(kpi_name)
        self._contamination = contamination
        self._n_estimators = n_estimators
        self._model_dir = model_dir or Path("data/models")
        self._model: IsolationForest | None = None
        self._scaler: StandardScaler | None = None

    def _engineer_features(self, series: pd.Series) -> pd.DataFrame:
        df = pd.DataFrame({"value": series})
        df["lag_7"] = df["value"].shift(7)
        df["lag_14"] = df["value"].shift(14)
        df["roll_mean_7"] = df["value"].rolling(7, min_periods=1).mean()
        df["roll_std_30"] = df["value"].rolling(30, min_periods=5).std().fillna(1.0)
        df["deviation"] = df["value"] - df["roll_mean_7"]
        return df.fillna(method="bfill").fillna(method="ffill")  # type: ignore[call-arg]

    def fit(self, historical: pd.DataFrame) -> None:
        features = self._engineer_features(historical["value"].astype(float))
        self._scaler = StandardScaler()
        scaled = self._scaler.fit_transform(features.values)
        self._model = IsolationForest(
            n_estimators=self._n_estimators,
            contamination=self._contamination,
            random_state=42,
        )
        self._model.fit(scaled)
        self._is_fitted = True
        logger.info(
            "IsolationForest fitted for %s on %d rows", self._kpi_name, len(historical)
        )

    def detect(self, current: pd.DataFrame) -> list[AnomalyResult]:
        self._require_fitted()
        assert self._model is not None and self._scaler is not None

        features = self._engineer_features(current["value"].astype(float))
        scaled = self._scaler.transform(features.values)
        scores = self._model.decision_function(scaled)
        predictions = self._model.predict(scaled)

        results = []
        for i, (_, row) in enumerate(current.iterrows()):
            if predictions[i] == -1:
                # decision_function returns negative scores for anomalies;
                # invert and normalize so higher = more anomalous
                raw_score = float(-scores[i])
                severity = min(1.0, max(0.0, raw_score / 0.5))
                results.append(
                    AnomalyResult(
                        kpi_name=self._kpi_name,
                        detected_at=datetime.now(tz=UTC),
                        period_start=row["period_start"],
                        period_end=row["period_end"],
                        observed_value=float(row["value"]),
                        expected_range=(0.0, 0.0),  # IF doesn't produce explicit bounds
                        severity=severity,
                        detector_name=self.name,
                        entity=str(row.get("entity", "global")),
                        context={"if_score": round(float(scores[i]), 4)},
                    )
                )
        return results
