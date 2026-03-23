"""
CSV/Excel ingestion loader — parses raw export files into dicts ready for validation.

Supports two file formats:
- CSV: one row per KPI measurement, columns match the ingestion schema
- Excel: first sheet only, same column expectations as CSV

The loader is intentionally thin — it reads and coerces types, nothing more.
Validation of business rules (value ranges, date logic, KPI name registry) is the
responsibility of validator.py downstream.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pandas as pd

REQUIRED_COLUMNS = {
    "kpi_name",
    "period_start",
    "period_end",
    "value",
    "unit",
    "entity",
    "source",
}


def load_file(file_path: str | Path) -> list[dict[str, Any]]:
    """
    Parse a CSV or Excel file into a list of raw record dicts.

    Raises:
        ValueError: if the file extension is unsupported or required columns are
            missing.
        FileNotFoundError: if the path does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Ingestion file not found: {path}")

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, parse_dates=["period_start", "period_end"])
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(
            path, sheet_name=0, parse_dates=["period_start", "period_end"]
        )
    else:
        raise ValueError(
            f"Unsupported file format: {path.suffix}. Expected .csv or .xlsx"
        )

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    # pandas-stubs widens to_dict() keys to Hashable, but CSV/Excel column
    # headers are always strings — cast is semantically correct here.
    return cast(list[dict[str, Any]], df.to_dict(orient="records"))
