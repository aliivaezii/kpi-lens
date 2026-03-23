"""
Command Center — top-level KPI health dashboard.

Shows all 8 KPIs as metric cards with RAG status, trend arrows, and
benchmark distance. Active anomalies are surfaced below the grid.
"""

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.title("🏠 Supply Chain Command Center")
st.caption("Live KPI health across all monitored metrics")


# ── Fetch data ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)  # Refresh every 5 minutes
def fetch_snapshot() -> dict[str, Any]:
    try:
        resp = httpx.get(f"{API_BASE}/api/kpis/snapshot", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        st.error(f"Cannot reach API: {exc}")
        return {}


@st.cache_data(ttl=300)
def fetch_anomalies() -> list[dict[str, Any]]:
    try:
        resp = httpx.get(
            f"{API_BASE}/api/anomalies?days_back=7&severity_floor=0.3",
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


snapshot = fetch_snapshot()
anomalies = fetch_anomalies()

# ── KPI Grid ──────────────────────────────────────────────────────────────────
STATUS_EMOJI = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
TREND_ARROW = {"up": "↑", "down": "↓", "stable": "→"}

if snapshot:
    cols = st.columns(4)
    for i, (kpi_name, data) in enumerate(snapshot.items()):
        with cols[i % 4]:
            status = data.get("health_status", "unknown")
            emoji = STATUS_EMOJI.get(status, "⚪")
            mom_delta = data.get("mom_delta", 0.0)
            if mom_delta > 0:
                arrow = TREND_ARROW["up"]
            elif mom_delta < 0:
                arrow = TREND_ARROW["down"]
            else:
                arrow = TREND_ARROW["stable"]

            st.metric(
                label=f"{emoji} {data.get('display_name', kpi_name)}",
                value=f"{data.get('value', '—')} {data.get('unit', '')}",
                delta=f"{mom_delta:+.1f}% MoM" if mom_delta else None,
                delta_color="normal"
                if data.get("direction") == "higher_is_better"
                else "inverse",
            )
            st.caption(
                f"Benchmark: {data.get('benchmark', '—')} {data.get('unit', '')} | "
                f"vs industry: {data.get('benchmark_distance', 0):+.1f}%"
            )

# ── Active Anomalies ──────────────────────────────────────────────────────────
st.divider()
st.subheader(f"⚠️ Active Anomalies — Last 7 Days ({len(anomalies)})")

if anomalies:
    for a in anomalies[:5]:
        severity_pct = int(a.get("severity", 0) * 100)
        if severity_pct >= 70:
            color = "red"
        elif severity_pct >= 40:
            color = "orange"
        else:
            color = "yellow"
        with st.expander(
            f"{a.get('kpi_name', '').upper()} | Severity {severity_pct}% | "
            f"{a.get('period_start', '')}",
            expanded=severity_pct >= 70,
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Observed", f"{a.get('observed_value', '—')}")
                exp_low = a.get("expected_low", "—")
                exp_high = a.get("expected_high", "—")
                st.metric("Expected Range", f"{exp_low} – {exp_high}")
            with col2:
                st.metric("Detector", a.get("detector_name", "—"))
                if a.get("llm_narrative"):
                    st.info(a["llm_narrative"][:300] + "…")
                else:
                    st.caption("LLM analysis pending…")
else:
    st.success("No anomalies detected in the last 7 days.")

# ── Refresh control ───────────────────────────────────────────────────────────
with st.sidebar:
    st.divider()
    if st.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Auto-refreshes every 5 minutes")
