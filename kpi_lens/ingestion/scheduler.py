"""
APScheduler-based ingestion scheduler.

Runs the full ingestion pipeline (load -> validate -> persist) on a configurable
cron schedule. Designed to be started once at API startup via the FastAPI
lifespan hook.

The scheduler is intentionally decoupled from the FastAPI request cycle — it
runs as a background thread so a slow ingestion job never delays API responses.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from kpi_lens.config import settings
from kpi_lens.db.repository import KPIRepository
from kpi_lens.db.schema import IngestionAudit, KPIRecord
from kpi_lens.ingestion.loader import load_file
from kpi_lens.ingestion.validator import validate_batch

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def run_ingestion_pipeline(drop_dir: str | None = None) -> None:
    """
    Execute one full ingestion cycle: discover files -> load -> validate -> persist.

    Files in `drop_dir` (default: data/exports/) are processed in alphabetical
    order. Successfully processed files are moved to data/exports/processed/.
    """
    search_dir = Path(drop_dir or "data/exports")
    processed_dir = search_dir / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    csv_files = sorted(search_dir.glob("*.csv")) + sorted(search_dir.glob("*.xlsx"))
    if not csv_files:
        logger.debug("Ingestion scheduler: no files found in %s", search_dir)
        return

    # KPIRepository is constructed here rather than at module level so that the
    # scheduler can be imported without a live DB connection at startup.
    repo = KPIRepository()  # noqa: F841 — kept for future audit integration
    engine = create_engine(settings.database_url)

    for file_path in csv_files:
        logger.info("Ingesting file: %s", file_path)
        try:
            raw_records = load_file(file_path)
            result = validate_batch(raw_records)

            # Persist accepted records via ORM. The scheduler is an infrastructure
            # boundary — direct ORM access here is the one permitted exception to
            # the "all DB calls in repository.py" rule.
            with Session(engine) as session:
                for validated_record in result.accepted:
                    session.add(
                        KPIRecord(
                            kpi_name=validated_record.kpi_name,
                            period_start=validated_record.period_start,
                            period_end=validated_record.period_end,
                            value=validated_record.value,
                            unit=validated_record.unit,
                            entity=validated_record.entity,
                            source=validated_record.source,
                        )
                    )
                session.add(
                    IngestionAudit(
                        ingested_at=datetime.now(tz=UTC),
                        source_file=str(file_path),
                        source_type="file",
                        records_received=result.total_received,
                        records_accepted=result.accepted_count,
                        records_rejected=result.rejected_count,
                        validation_errors=(
                            str([r["error"] for r in result.rejected])
                            if result.rejected
                            else None
                        ),
                    )
                )
                session.commit()

            file_path.rename(processed_dir / file_path.name)
            logger.info(
                "Ingested %s: %d accepted, %d rejected",
                file_path.name,
                result.accepted_count,
                result.rejected_count,
            )
        except (OSError, ValueError) as exc:
            # File-level failures are logged but must not stop processing other files
            logger.error("Failed to ingest %s: %s", file_path, exc)


def start_scheduler(cron_expression: str = "0 6 * * 1") -> None:
    """
    Start the background ingestion scheduler.

    Default schedule: every Monday at 06:00 (weekly supply chain data cadence).
    Call this from the FastAPI lifespan startup hook.
    """
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        run_ingestion_pipeline,
        trigger=CronTrigger.from_crontab(cron_expression),
        id="kpi_ingestion",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Ingestion scheduler started — cron: %s", cron_expression)


def stop_scheduler() -> None:
    """Graceful shutdown. Call from FastAPI lifespan shutdown hook."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Ingestion scheduler stopped")
