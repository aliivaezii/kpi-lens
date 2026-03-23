"""
The 8 supply chain KPI constants — the single registry for the entire application.

Import these constants everywhere a KPI name or threshold is needed.
Never use bare string literals like "otif" outside this module.

Usage:
    from kpi_lens.kpis.definitions import OTIF, ALL_KPIS
    print(OTIF.name)                   # "otif"
    print(OTIF.green_threshold)        # 95.0
    for kpi in ALL_KPIS:
        print(kpi.display_name)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DirectionType = Literal["higher_is_better", "lower_is_better"]


@dataclass(frozen=True)
class KPIDefinition:
    """
    Immutable descriptor for a single KPI.

    Frozen so that constants cannot be accidentally mutated at runtime.
    All threshold values are the "company internal" targets; industry_benchmark
    is the external P50 from the relevant industry report.
    """

    name: str
    display_name: str
    unit: str
    direction: DirectionType
    green_threshold: float
    yellow_threshold: float
    red_threshold: float
    industry_benchmark: float
    # Non-None means STL seasonal decomposition is applied before anomaly detection.
    # Value is the expected seasonality period in days (e.g. 365 for annual).
    seasonality_period: int | None
    description: str

    def health_status(self, value: float) -> Literal["green", "yellow", "red"]:
        """Map a raw KPI value to a RAG status using this KPI's thresholds."""
        if self.direction == "higher_is_better":
            if value >= self.green_threshold:
                return "green"
            if value >= self.yellow_threshold:
                return "yellow"
            return "red"
        else:
            if value <= self.green_threshold:
                return "green"
            if value <= self.yellow_threshold:
                return "yellow"
            return "red"

    def distance_from_benchmark(self, value: float) -> float:
        """
        Signed percentage distance from the industry benchmark.

        Positive = better than benchmark, negative = worse.
        Accounts for direction so the sign is always interpretable the same way.
        """
        if self.industry_benchmark == 0:
            return 0.0
        raw_pct = (value - self.industry_benchmark) / self.industry_benchmark * 100
        return raw_pct if self.direction == "higher_is_better" else -raw_pct


# ── KPI Constants ─────────────────────────────────────────────────────────────

OTIF = KPIDefinition(
    name="otif",
    display_name="OTIF Delivery Rate",
    unit="%",
    direction="higher_is_better",
    green_threshold=95.0,
    yellow_threshold=90.0,
    red_threshold=85.0,
    industry_benchmark=95.5,
    seasonality_period=None,
    description="% orders delivered on-time and in-full.",
)

INVENTORY_TURN = KPIDefinition(
    name="inventory_turn",
    display_name="Inventory Turnover",
    unit="turns/yr",
    direction="higher_is_better",
    green_threshold=12.0,
    yellow_threshold=8.0,
    red_threshold=5.0,
    industry_benchmark=10.0,
    seasonality_period=365,
    description="Times inventory is sold and replaced per year.",
)

DIO = KPIDefinition(
    name="dio",
    display_name="Days Inventory Outstanding",
    unit="days",
    direction="lower_is_better",
    green_threshold=30.0,
    yellow_threshold=45.0,
    red_threshold=60.0,
    industry_benchmark=35.0,
    seasonality_period=365,
    description="Average days to sell all inventory on hand.",
)

SUPPLIER_DPPM = KPIDefinition(
    name="supplier_dppm",
    display_name="Supplier DPPM",
    unit="ppm",
    direction="lower_is_better",
    green_threshold=500.0,
    yellow_threshold=1500.0,
    red_threshold=3000.0,
    industry_benchmark=800.0,
    seasonality_period=None,
    description="Defective parts per million from suppliers.",
)

DFA = KPIDefinition(
    name="dfa",
    display_name="Demand Forecast Accuracy",
    unit="%",
    direction="higher_is_better",
    green_threshold=85.0,
    yellow_threshold=75.0,
    red_threshold=65.0,
    industry_benchmark=80.0,
    seasonality_period=365,
    description="Accuracy of demand forecasts vs. actual demand.",
)

FILL_RATE = KPIDefinition(
    name="fill_rate",
    display_name="Order Fill Rate",
    unit="%",
    direction="higher_is_better",
    green_threshold=97.0,
    yellow_threshold=93.0,
    red_threshold=88.0,
    industry_benchmark=96.0,
    seasonality_period=None,
    description="% order lines shipped complete from available stock.",
)

LTV = KPIDefinition(
    name="ltv",
    display_name="Lead Time Variance",
    unit="days",
    direction="lower_is_better",
    green_threshold=3.0,
    yellow_threshold=7.0,
    red_threshold=14.0,
    industry_benchmark=5.0,
    seasonality_period=None,
    description="Std deviation of supplier lead times over 90-day window.",
)

PO_CYCLE_TIME = KPIDefinition(
    name="po_cycle_time",
    display_name="PO Cycle Time",
    unit="days",
    direction="lower_is_better",
    green_threshold=14.0,
    yellow_threshold=21.0,
    red_threshold=30.0,
    industry_benchmark=18.0,
    seasonality_period=None,
    description="Average days from PO creation to goods receipt.",
)

# Ordered tuple — defines the canonical display order throughout the application
ALL_KPIS: tuple[KPIDefinition, ...] = (
    OTIF,
    FILL_RATE,
    DFA,
    INVENTORY_TURN,
    DIO,
    SUPPLIER_DPPM,
    LTV,
    PO_CYCLE_TIME,
)

# Lookup map for O(1) access by name
KPI_BY_NAME: dict[str, KPIDefinition] = {kpi.name: kpi for kpi in ALL_KPIS}
