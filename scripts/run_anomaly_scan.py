"""
Run one full anomaly detection cycle across all KPIs.

Loads the latest 90 days of data per KPI, fits the ensemble detector on
historical data, and persists any detected anomalies to the database.

Run:
    python scripts/run_anomaly_scan.py
    python scripts/run_anomaly_scan.py --kpi otif          # single KPI
    python scripts/run_anomaly_scan.py --weeks-back 12     # use 12 weeks of history
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parent.parent))

from kpi_lens.anomaly.ensemble import EnsembleDetector  # noqa: E402
from kpi_lens.config import settings  # noqa: E402
from kpi_lens.db.repository import KPIRepository  # noqa: E402
from kpi_lens.db.schema import AnomalyEvent  # noqa: E402
from kpi_lens.kpis.definitions import ALL_KPIS, KPI_BY_NAME  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def scan_kpi(kpi_name: str, repo: KPIRepository, weeks_back: int) -> int:
    """
    Run ensemble detection on the most recent 'weeks_back' weeks of data.
    Returns the number of anomalies persisted.
    """
    end = date.today()
    # +4 weeks of buffer so the fit window has a full period boundary before
    # the current evaluation window — prevents data leakage at the boundary.
    start = end - timedelta(weeks=weeks_back + 4)
    history_cutoff = end - timedelta(weeks=4)

    df = repo.get_kpi_series(kpi_name, start, end)
    if len(df) < 10:
        logger.warning("Skipping %s — insufficient data (%d rows)", kpi_name, len(df))
        return 0

    # Convert to datetime for comparison — repository returns date objects which
    # pandas stores as object dtype, incompatible with pd.Timestamp comparisons.
    dates = pd.to_datetime(df["period_end"])
    cutoff_ts = pd.Timestamp(history_cutoff)
    historical = df[dates <= cutoff_ts]
    current = df[dates > cutoff_ts]

    if current.empty:
        logger.warning("Skipping %s — no current-period data", kpi_name)
        return 0

    detector = EnsembleDetector(kpi_name)
    detector.fit(historical)
    results = detector.detect(current)

    engine = create_engine(settings.database_url)
    persisted = 0
    with Session(engine) as session:
        for result in results:
            if result.severity < 0.3:
                # Below severity floor — log at DEBUG and skip persistence
                logger.debug("Below floor: %s severity=%.2f", kpi_name, result.severity)
                continue
            row = current[current["period_end"] == result.period_end].iloc[0]
            period_start_val = row["period_start"]
            period_end_val = result.period_end
            session.add(
                AnomalyEvent(
                    kpi_name=kpi_name,
                    detected_at=datetime.now(tz=UTC),
                    period_start=(
                        period_start_val.date()
                        if hasattr(period_start_val, "date")
                        else period_start_val
                    ),
                    period_end=(
                        period_end_val
                        if isinstance(period_end_val, date)
                        else period_end_val.date()
                    ),
                    observed_value=result.observed_value,
                    expected_low=result.expected_range[0],
                    expected_high=result.expected_range[1],
                    severity=result.severity,
                    detector_name=result.detector_name,
                    entity=result.entity,
                )
            )
            persisted += 1
        session.commit()

    return persisted


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run anomaly detection across all KPIs"
    )
    parser.add_argument("--kpi", type=str, default=None, help="Limit to one KPI name")
    parser.add_argument(
        "--weeks-back",
        type=int,
        default=12,
        help="Weeks of history to use (default: 12)",
    )
    args = parser.parse_args()

    if args.kpi and args.kpi not in KPI_BY_NAME:
        logger.error("Unknown KPI: %s. Valid names: %s", args.kpi, sorted(KPI_BY_NAME))
        sys.exit(1)

    kpis_to_scan = [KPI_BY_NAME[args.kpi]] if args.kpi else list(ALL_KPIS)

    repo = KPIRepository()
    total_anomalies = 0
    for kpi in kpis_to_scan:
        count = scan_kpi(kpi.name, repo, args.weeks_back)
        logger.info("%-20s -> %d anomalies detected", kpi.name, count)
        total_anomalies += count

    logger.info("Scan complete — %d total anomalies persisted", total_anomalies)


if __name__ == "__main__":
    main()
