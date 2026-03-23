"""Unit tests for KPI definitions and threshold logic."""

from __future__ import annotations

import pytest

from kpi_lens.kpis.definitions import (
    ALL_KPIS,
    DIO,
    KPI_BY_NAME,
    LTV,
    OTIF,
    SUPPLIER_DPPM,
    KPIDefinition,
)


def test_all_kpis_registered() -> None:
    assert len(ALL_KPIS) == 8
    assert len(KPI_BY_NAME) == 8


def test_kpi_by_name_lookup() -> None:
    assert KPI_BY_NAME["otif"] is OTIF
    assert KPI_BY_NAME["dio"] is DIO
    assert KPI_BY_NAME["ltv"] is LTV


def test_all_kpi_names_match_dict_keys() -> None:
    for kpi in ALL_KPIS:
        assert kpi.name in KPI_BY_NAME
        assert KPI_BY_NAME[kpi.name] is kpi


# ── health_status — higher_is_better ──────────────────────────────────────────


def test_otif_green_at_or_above_green_threshold() -> None:
    assert OTIF.health_status(97.0) == "green"
    assert OTIF.health_status(95.0) == "green"  # exactly at boundary


def test_otif_yellow_between_thresholds() -> None:
    assert OTIF.health_status(92.0) == "yellow"
    assert OTIF.health_status(90.0) == "yellow"  # exactly at boundary


def test_otif_red_below_yellow_threshold() -> None:
    assert OTIF.health_status(89.9) == "red"
    assert OTIF.health_status(78.0) == "red"


# ── health_status — lower_is_better ───────────────────────────────────────────


def test_dio_green_at_or_below_green_threshold() -> None:
    assert DIO.health_status(25.0) == "green"
    assert DIO.health_status(30.0) == "green"


def test_dio_yellow_between_thresholds() -> None:
    assert DIO.health_status(40.0) == "yellow"
    assert DIO.health_status(45.0) == "yellow"


def test_dio_red_above_yellow_threshold() -> None:
    assert DIO.health_status(50.0) == "red"
    assert DIO.health_status(65.0) == "red"


def test_supplier_dppm_health_status() -> None:
    assert SUPPLIER_DPPM.health_status(400.0) == "green"
    assert SUPPLIER_DPPM.health_status(1000.0) == "yellow"
    assert SUPPLIER_DPPM.health_status(5000.0) == "red"


# ── distance_from_benchmark ───────────────────────────────────────────────────


def test_distance_positive_when_above_benchmark_higher_is_better() -> None:
    # OTIF benchmark = 95.5; value = 100 is above
    dist = OTIF.distance_from_benchmark(100.0)
    assert dist > 0.0


def test_distance_negative_when_below_benchmark_higher_is_better() -> None:
    # OTIF benchmark = 95.5; value = 90 is below
    dist = OTIF.distance_from_benchmark(90.0)
    assert dist < 0.0


def test_distance_positive_when_below_benchmark_lower_is_better() -> None:
    # DIO benchmark = 35; value = 28 is better (lower)
    dist = DIO.distance_from_benchmark(28.0)
    assert dist > 0.0


def test_distance_negative_when_above_benchmark_lower_is_better() -> None:
    # DIO benchmark = 35; value = 50 is worse (higher)
    dist = DIO.distance_from_benchmark(50.0)
    assert dist < 0.0


def test_distance_zero_when_benchmark_is_zero() -> None:
    kpi = KPIDefinition(
        name="test",
        display_name="Test",
        unit="%",
        direction="higher_is_better",
        green_threshold=90.0,
        yellow_threshold=80.0,
        red_threshold=70.0,
        industry_benchmark=0.0,
        seasonality_period=None,
        description="sentinel KPI with zero benchmark",
    )
    assert kpi.distance_from_benchmark(85.0) == 0.0


def test_kpi_definition_is_frozen() -> None:
    with pytest.raises((AttributeError, TypeError)):
        OTIF.name = "mutated"  # type: ignore[misc]


def test_kpi_properties_consistent() -> None:
    for kpi in ALL_KPIS:
        assert isinstance(kpi.name, str) and kpi.name
        assert isinstance(kpi.unit, str)
        assert kpi.direction in ("higher_is_better", "lower_is_better")
        assert kpi.industry_benchmark >= 0
