# KPI-Lens

[![CI](https://github.com/aliivaezii/kpi-lens/actions/workflows/ci.yml/badge.svg)](https://github.com/aliivaezii/kpi-lens/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/aliivaezii/kpi-lens)](https://github.com/aliivaezii/kpi-lens/releases)
[![Deploy on Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/aliivaezii/kpi-lens)

> An AI-powered supply chain intelligence platform that monitors 8 operational KPIs,
> detects anomalies using an ensemble of statistical detectors, and explains root causes
> via Claude — all accessible through a Streamlit dashboard, FastAPI, and an MCP server.

Supply chain teams spend hours manually reviewing KPI dashboards and writing exception reports.
KPI-Lens automates the entire loop: ingest → detect → explain → report.
A single `docker compose up` gives you a live anomaly feed, LLM-generated root-cause narratives,
and one-click Excel/PPT exports ready for SteerCo.

## Features

- **8 supply chain KPIs** tracked weekly: OTIF, Fill Rate, DFA, Inventory Turnover, DIO, Supplier DPPM, Lead Time Variance, PO Cycle Time
- **Ensemble anomaly detection**: Z-score + IQR + CUSUM + Isolation Forest detectors with weighted voting
- **LLM root-cause analysis**: Claude generates narrative explanations and recommended actions for each anomaly
- **FastAPI backend** with 10+ endpoints for KPI data, anomaly management, and LLM chat
- **Streamlit dashboard** with 5 pages: Command Center, KPI Deep Dive, Anomaly Log, LLM Analyst, Reports
- **MCP server** for Claude Desktop integration — query live KPI data conversationally
- **Automated ingestion**: CSV/Excel file watcher with Pydantic v2 validation and APScheduler cron
- **Report generation**: Excel workbooks and PowerPoint decks for SteerCo presentations
- **80%+ test coverage** across unit and integration tests; CI runs on Python 3.11 + 3.12

## Quick Start

### Docker Compose (recommended)

```bash
git clone https://github.com/aliivaezii/kpi-lens.git
cd kpi-lens
cp .env.example .env          # Add your ANTHROPIC_API_KEY
docker compose up -d api dashboard

# Seed 2 years of synthetic KPI data (first run only)
docker compose run --rm api python scripts/seed_database.py

# Open the dashboard
open http://localhost:8501
```

### Local Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # Add your ANTHROPIC_API_KEY

# Seed the database
python data/seeds/generate_kpis.py

# Start services (three terminals)
uvicorn kpi_lens.api.main:app --reload --port 8000
streamlit run kpi_lens/dashboard/app.py
python -m kpi_lens.mcp_server.server   # optional: MCP for Claude Desktop
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  External Sources (CSV/Excel exports from ERP)              │
└──────────────────────────┬──────────────────────────────────┘
                           │ ingestion/loader.py + validator.py
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  SQLite DB  ←──  db/repository.py (only DB gateway)        │
└──────┬────────────────────────────────────────────────────┬─┘
       │                                                    │
       ▼                                                    ▼
┌─────────────────────┐                     ┌──────────────────────────┐
│  anomaly/ensemble   │   AnomalyResult     │  api/  (FastAPI)         │
│  ┣ threshold        │ ────────────────►   │  dashboard/ (Streamlit)  │
│  ┣ zscore/iqr/cusum │                     │  mcp_server/ (FastMCP)   │
│  ┗ isolation forest │                     └──────────────────────────┘
└─────────┬───────────┘
          │ async (non-blocking)
          ▼
┌─────────────────────────────────────────────────────────────┐
│  llm/analyst.py  →  Claude via Anthropic SDK               │
│  Generates narrative + recommended actions per anomaly      │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│  reporting/  →  Excel workbook  +  PowerPoint deck          │
└─────────────────────────────────────────────────────────────┘
```

## KPI Reference

| KPI | Unit | Direction | Green threshold | Industry Benchmark |
|---|---|---|---|---|
| OTIF Delivery Rate | % | Higher is better | 95% | 95.5% |
| Order Fill Rate | % | Higher is better | 97% | 96% |
| Demand Forecast Accuracy | % | Higher is better | 85% | 80% |
| Inventory Turnover | turns/yr | Higher is better | 12 | 10 |
| Days Inventory Outstanding | days | Lower is better | 30 | 35 |
| Supplier DPPM | ppm | Lower is better | 500 | 800 |
| Lead Time Variance | days | Lower is better | 3 | 5 |
| PO Cycle Time | days | Lower is better | 14 | 18 |

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/kpis/snapshot` | Latest value + health status for all 8 KPIs |
| GET | `/api/kpis/{name}/series` | Time-series data for one KPI |
| GET | `/api/kpis/{name}/entities` | Entity (supplier) breakdown |
| GET | `/api/kpis/{name}/benchmarks` | Industry benchmark percentiles |
| GET | `/api/anomalies` | Recent anomalies with severity filter |
| POST | `/api/anomalies/{id}/acknowledge` | Acknowledge an anomaly |
| POST | `/api/llm/chat` | Chat with the supply chain analyst |
| POST | `/api/reports/enqueue` | Enqueue an anomaly report |

Interactive docs: `http://localhost:8000/api/docs`

## Project Structure

```
kpi_lens/
├── db/           # repository.py — the only DB gateway; schema.py — ORM models
├── kpis/         # definitions.py — 8 KPI constants; snapshot.py — enrichment
├── anomaly/      # base.py, threshold, statistical, ml, ensemble detectors
├── llm/          # client.py (retry), analyst.py, context_builder.py, prompts.py
├── ingestion/    # loader.py, validator.py (Pydantic v2), scheduler.py (APScheduler)
├── reporting/    # excel_exporter.py, powerpoint.py, pdf_converter.py
├── api/          # FastAPI app + routes (kpis, anomalies, llm, reports, health)
├── dashboard/    # Streamlit app + 5 pages
└── mcp_server/   # FastMCP tools for Claude Desktop
config/           # kpis.yaml, anomaly.yaml, report.yaml (change without redeploy)
scripts/          # seed_database.py, run_anomaly_scan.py
tests/
├── unit/         # 8 test files, 70+ tests, no I/O
└── integration/  # FastAPI test client, in-memory DB, mocked LLM
```

## Running Tests

```bash
# Unit tests (fast, no infrastructure needed)
pytest tests/unit/ -v --cov=kpi_lens --cov-fail-under=80

# Integration tests (FastAPI + in-memory DB)
pytest tests/integration/ -v

# All tests
pytest tests/ -v --cov=kpi_lens --cov-fail-under=80
```

## Seeding Data

```bash
# Default: 104 weeks (2 years) of synthetic data for all 8 KPIs
python scripts/seed_database.py

# Custom parameters
python scripts/seed_database.py --weeks 52

# Run anomaly detection on seeded data
python scripts/run_anomaly_scan.py
```

## Deployment

### Render (full stack — API + Dashboard)

Click **Deploy on Render** above or create a `Web Service` pointing to this repo.
Render reads `render.yaml` automatically. Set `ANTHROPIC_API_KEY` in the environment
variables panel before deploying.

### Streamlit Community Cloud (dashboard only)

1. Fork this repo
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Set **Main file path**: `kpi_lens/dashboard/app.py`
4. Under **Advanced settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   DATABASE_URL = "sqlite:///kpi_lens.db"
   ```
5. Deploy — Streamlit seeds the demo DB on first run

### Docker Compose (self-hosted)

```bash
git clone https://github.com/aliivaezii/kpi-lens.git
cd kpi-lens
cp .env.example .env   # add ANTHROPIC_API_KEY
docker compose up -d api dashboard
docker compose run --rm api python scripts/seed_database.py
open http://localhost:8501
```

## Data

The platform ships with a realistic **synthetic dataset** generated by `data/seeds/generate_kpis.py`:
- 104 weeks × 8 KPIs × 5 supplier entities = 4,160 weekly records
- Additive model with seasonality, trend, and deliberate anomaly injection at known dates
- Designed to exercise all four detector types (threshold, Z-score, IQR, CUSUM)

To use your own data, drop a CSV into `data/imports/` and run the ingestion scheduler,
or POST directly to `POST /api/ingest`. Format reference: `data/samples/sample_kpi_data.csv`.

## License

MIT — see [LICENSE](LICENSE).
