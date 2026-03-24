# Changelog

All notable changes to KPI-Lens are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.1.0] — 2026-03-23

### Added

**Core data layer**
- SQLAlchemy 2.0 schema: `kpi_records`, `anomaly_events`, `ingestion_audit`,
  `report_log` tables with partial indexes for unacknowledged anomaly queries
- `KPIRepository` — single DB gateway; all other modules receive plain Python
  objects, never ORM instances
- 8 KPI definitions (OTIF, Inventory Turnover, DIO, Supplier DPPM, DFA,
  Fill Rate, LTV, PO Cycle Time) with thresholds and industry benchmarks

**Ingestion pipeline**
- CSV/Excel loader with Pydantic v2 validation (`InboundKPIRecord`)
- APScheduler weekly cron (Monday 06:00) for automated file ingestion
- Synthetic seed script: 104 weeks × 8 KPIs × 5 suppliers with injected
  anomalies at known dates for detector validation

**Anomaly detection**
- Z-score and IQR detectors, ensemble with configurable weights
- `AnomalyDetector` ABC for adding new detectors without changing the ensemble

**REST API (FastAPI)**
- `GET  /api/kpis/snapshot` — current health status for all KPIs
- `GET  /api/kpis/{name}/series` — paginated time-series with entity filter
- `GET  /api/kpis/{name}/entities` — per-supplier breakdown
- `GET  /api/kpis/{name}/benchmarks` — industry percentile comparison
- `GET  /api/anomalies/` — recent events with severity floor filter
- `POST /api/anomalies/{id}/acknowledge` — mark anomaly reviewed
- `POST /api/llm/chat` — direct analyst chat endpoint
- `POST /api/reports/enqueue` — async report generation trigger

**MCP Server (FastMCP)**
- 6 read-only tools: `get_kpi_schema`, `get_kpi_snapshot`, `get_kpi_time_series`,
  `get_recent_anomalies`, `compare_to_benchmark`, `get_supplier_breakdown`
- 1 enqueue-only tool: `trigger_report`

**Reporting**
- Excel workbook: Executive Summary (RAG colouring), Anomaly Detail,
  KPI Trends pivot — generated as in-memory bytes, no temp files
- PowerPoint deck: title slide, KPI health table, anomaly bullet list

**LLM layer**
- `SupplyChainAnalyst` wrapping the Anthropic SDK
- Async enrichment pattern — anomaly is persisted before LLM call;
  a failed or slow API response never blocks the detection pipeline

**Streamlit dashboard**
- KPI overview with traffic-light health cards
- Anomaly timeline with acknowledge action
- Report trigger and download

**CI / CD**
- GitHub Actions pipeline: ruff format, ruff check, mypy, unit tests (3.11 +
  3.12, 80% coverage gate), integration tests (17 async tests), Docker builds
- Three Dockerfiles (API, Dashboard, MCP) with multi-stage builds
- `docker-compose.yml` with named service profiles

**Developer tooling**
- `.claude/` project configuration with architecture rules, coding standards,
  testing standards, and git worktree policy
- `.env.example` with placeholder values only — no real credentials

---

[0.2.1]: https://github.com/aliivaezii/kpi-lens/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/aliivaezii/kpi-lens/compare/v0.1.2...v0.2.0
[0.1.2]: https://github.com/aliivaezii/kpi-lens/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/aliivaezii/kpi-lens/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/aliivaezii/kpi-lens/releases/tag/v0.1.0
