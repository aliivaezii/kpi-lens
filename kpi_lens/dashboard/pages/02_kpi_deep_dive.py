"""
KPI Deep Dive — detailed time-series analysis for a single KPI.

Provides: interactive time-series chart, entity breakdown bar chart,
benchmark comparison, and health status history.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

API_BASE = "http://localhost:8000"

# ── KPI selector and time range (sidebar) ─────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    kpi_options = {
        "OTIF Delivery Rate": "otif",
        "Order Fill Rate": "fill_rate",
        "Demand Forecast Accuracy": "dfa",
        "Inventory Turnover": "inventory_turn",
        "Days Inventory Outstanding": "dio",
        "Supplier DPPM": "supplier_dppm",
        "Lead Time Variance": "ltv",
        "PO Cycle Time": "po_cycle_time",
    }
    selected_display = st.selectbox("KPI", list(kpi_options.keys()))
    selected_kpi = kpi_options[selected_display]

    end_date = date.today()
    start_date = end_date - timedelta(weeks=52)
    date_range = st.date_input(
        "Date range",
        value=(start_date, end_date),
        max_value=end_date,
    )
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range[0], date_range[1]

    entity = st.selectbox(
        "Entity",
        [
            "global",
            "supplier:Bosch",
            "supplier:Continental",
            "supplier:Magna",
            "supplier:ZF",
            "supplier:Aptiv",
        ],
    )

st.title(f"📊 {selected_display}")
st.caption(f"Detailed analysis · {start_date} → {end_date}")


# ── Data fetching ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_series(kpi: str, start: date, end: date, ent: str) -> list[dict[str, Any]]:
    try:
        resp = httpx.get(
            f"{API_BASE}/api/kpis/{kpi}/series",
            params={"start": str(start), "end": str(end), "entity": ent},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
    except Exception as exc:
        st.error(f"Cannot reach API: {exc}")
        return []


@st.cache_data(ttl=300)
def fetch_entities(kpi: str, start: date, end: date) -> list[dict[str, Any]]:
    try:
        resp = httpx.get(
            f"{API_BASE}/api/kpis/{kpi}/entities",
            params={"start": str(start), "end": str(end)},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
    except Exception:
        return []


@st.cache_data(ttl=3600)
def fetch_benchmarks(kpi: str) -> dict[str, Any]:
    try:
        resp = httpx.get(f"{API_BASE}/api/kpis/{kpi}/benchmarks", timeout=10)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
    except Exception:
        return {}


series_data = fetch_series(selected_kpi, start_date, end_date, entity)
entity_data = fetch_entities(selected_kpi, start_date, end_date)
benchmarks = fetch_benchmarks(selected_kpi)

# ── Time-series chart ──────────────────────────────────────────────────────────
if series_data:
    df = pd.DataFrame(series_data)
    df["period_end"] = pd.to_datetime(df["period_end"])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["period_end"],
            y=df["value"],
            mode="lines+markers",
            name=selected_display,
            line=dict(color="#1f77b4", width=2),
            marker=dict(size=4),
        )
    )

    # Add threshold bands using shapes (more performant than filled traces for
    # long series)
    if benchmarks:
        fig.add_hline(
            y=benchmarks.get("p50", 0),
            line_dash="dot",
            line_color="gray",
            annotation_text="Industry P50",
            annotation_position="bottom right",
        )

    fig.update_layout(
        xaxis_title="Period End",
        yaxis_title="Value",
        hovermode="x unified",
        height=380,
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info(
        "No time-series data available for the selected range. "
        "Run the seed script first."
    )

# ── Entity breakdown ───────────────────────────────────────────────────────────
st.subheader("Entity Breakdown")
if entity_data:
    entity_df = pd.DataFrame(entity_data)
    entity_df = entity_df.sort_values("value", ascending=True)
    fig_bar = go.Figure(
        go.Bar(
            x=entity_df["value"],
            y=entity_df["entity"],
            orientation="h",
            marker_color="#ff7f0e",
        )
    )
    fig_bar.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.caption("No supplier-level breakdown available for this KPI.")

# ── Benchmarks ────────────────────────────────────────────────────────────────
st.subheader("Industry Benchmarks")
if benchmarks:
    cols = st.columns(4)
    for col, (label, key) in zip(
        cols,
        [("P25", "p25"), ("P50", "p50"), ("P75", "p75"), ("P90", "p90")],
        strict=True,
    ):
        with col:
            val = benchmarks.get(key)
            st.metric(label, f"{val:.1f}" if val is not None else "—")
else:
    st.caption("No benchmark data available.")

with st.sidebar:
    st.divider()
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()
