# Contributing to KPI-Lens

## Development Setup

```bash
# Clone and create a virtual environment
git clone https://github.com/<you>/kpi-lens.git
cd kpi-lens
python -m venv .venv && source .venv/bin/activate

# Install all dev dependencies
pip install -e ".[dev]"

# Copy the example env and fill in your Anthropic API key
cp .env.example .env
```

## Running Tests

```bash
# Unit tests with coverage gate (80% required)
pytest tests/unit/ -v --cov=kpi_lens --cov-fail-under=80

# Integration tests — in-memory DB, mocked LLM, no real API calls
pytest tests/integration/ -v --no-cov

# Both together
pytest tests/ -v --no-cov
```

## Lint and Type Checks

```bash
# Formatter (must pass before committing)
python -m ruff format kpi_lens/

# Linter
python -m ruff check kpi_lens/

# Type checker
mypy kpi_lens/ --ignore-missing-imports
```

Run **both** `ruff format` and `ruff check` — the CI runs them as separate steps and
a passing lint does not mean format passes.

## Seeding Local Data

```bash
python -m kpi_lens.ingestion.seed
```

This generates ~104 weeks of synthetic KPI history for all 8 KPIs across 5 suppliers,
with injected anomalies at known dates for detector validation.

## Branch and Worktree Policy

The main clone stays on `main`, clean, and pull-ready at all times.
All feature work happens in a dedicated worktree:

```bash
git worktree add ../kpi-lens-<feature> -b feat/<feature>
cd ../kpi-lens-<feature>
# ... develop, commit, push, open PR ...
git worktree remove ../kpi-lens-<feature>
```

See `.claude/rules/git-policy.md` for the full policy.

## Architecture Constraints

Before submitting a PR, verify your changes comply with these invariants:

| Rule | Why |
|---|---|
| No DB calls outside `kpi_lens/db/repository.py` | Single point of change when the schema evolves |
| No LLM calls that block the anomaly pipeline | A slow Claude API call must never prevent anomaly logging |
| No credentials in source code | All secrets via `.env` → `kpi_lens/config.py` |
| No magic KPI name strings | Import from `kpi_lens.kpis.definitions` |
| MCP server is read-only | `report_trigger` enqueues; it never executes directly |

See `.claude/rules/architecture.md` for the full data-flow diagram and error-handling
policy.

## Pull Request Checklist

- [ ] `ruff format kpi_lens/` — no diff
- [ ] `ruff check kpi_lens/` — zero warnings
- [ ] `mypy kpi_lens/ --ignore-missing-imports` — zero errors
- [ ] `pytest tests/unit/ --cov=kpi_lens --cov-fail-under=80` — passes
- [ ] `pytest tests/integration/ --no-cov` — passes
- [ ] New public functions have full type annotations
- [ ] Comments explain *why*, not *what*
- [ ] No secrets or real API keys in any tracked file

## Reporting Issues

Open a GitHub Issue with:
- The Python version (`python --version`)
- The exact command that failed
- The full traceback
