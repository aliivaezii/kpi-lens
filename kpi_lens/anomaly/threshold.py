"""Hard rule-based threshold detector — always runs, regardless of history length."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from kpi_lens.anomaly.base import AnomalyDetector, AnomalyResult
from kpi_lens.kpis.definitions import KPI_BY_NAME


class ThresholdDetector(AnomalyDetector):
    """
    Fires when a KPI value crosses its red threshold (as defined in KPIDefinition).

    This is the only detector that runs with zero history. It provides immediate
    CRITICAL alerts for values that are clearly out of operational bounds,
    independent of recent trends.
    """

    def fit(self, historical: pd.DataFrame) -> None:
        # No fitting needed — thresholds come from the KPI definition constant
        self._is_fitted = True

    def detect(self, current: pd.DataFrame) -> list[AnomalyResult]:
        self._require_fitted()
        kpi = KPI_BY_NAME[self._kpi_name]
        results = []
        for _, row in current.iterrows():
            value = float(row["value"])
            status = kpi.health_status(value)
            if status == "red":
                # Severity 1.0 for red-threshold breaches — always above floor
                results.append(
                    AnomalyResult(
                        kpi_name=self._kpi_name,
                        detected_at=datetime.now(tz=UTC),
                        period_start=row["period_start"],
                        period_end=row["period_end"],
                        observed_value=value,
                        expected_range=(kpi.yellow_threshold, kpi.green_threshold)
                        if kpi.direction == "higher_is_better"
                        else (kpi.green_threshold, kpi.yellow_threshold),
                        severity=1.0,
                        detector_name=self.name,
                        entity=str(row.get("entity", "global")),
                        context={"threshold_type": "red", "status": status},
                    )
                )
        return results
