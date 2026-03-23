"""
Anomaly Log — filterable table of all detected anomalies with acknowledge actions.
"""

from __future__ import annotations

from typing import Any

import httpx
import pandas as pd
import streamlit as st

API_BASE = "http://localhost:8000"

st.title("⚠️ Anomaly Log")
st.caption("All detected KPI anomalies, ordered by severity")

# ── Filters ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    days_back = st.slider(
        "Look-back window (days)", min_value=7, max_value=90, value=30
    )
    severity_floor = st.slider(
        "Minimum severity", min_value=0.0, max_value=1.0, value=0.3, step=0.05
    )
    st.divider()
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()


@st.cache_data(ttl=120)
def fetch_anomalies(days: int, floor: float) -> list[dict[str, Any]]:
    try:
        resp = httpx.get(
            f"{API_BASE}/api/anomalies",
            params={"days_back": days, "severity_floor": floor},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]
    except Exception as exc:
        st.error(f"Cannot reach API: {exc}")
        return []


anomalies = fetch_anomalies(days_back, severity_floor)

if not anomalies:
    st.success("No anomalies matching current filters.")
    st.stop()

# ── Summary metrics ────────────────────────────────────────────────────────────
df = pd.DataFrame(anomalies)
col1, col2, col3 = st.columns(3)
col1.metric("Total Anomalies", len(df))
col2.metric("Avg Severity", f"{df['severity'].mean():.0%}")
col3.metric(
    "Acknowledged",
    int(df.get("is_acknowledged", pd.Series([False] * len(df))).sum()),
)

st.divider()

# ── Anomaly cards ──────────────────────────────────────────────────────────────
SEVERITY_COLOR = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
}


def severity_label(s: float) -> str:
    if s >= 0.7:
        return "critical"
    if s >= 0.4:
        return "high"
    return "medium"


for anomaly in anomalies:
    severity = anomaly.get("severity", 0)
    label = severity_label(severity)
    emoji = SEVERITY_COLOR[label]
    kpi = anomaly.get("kpi_name", "").upper()
    period = anomaly.get("period_start", "")
    acknowledged = anomaly.get("is_acknowledged", False)
    ack_badge = " ✅ Acknowledged" if acknowledged else ""

    with st.expander(
        f"{emoji} {kpi} | {label.capitalize()} ({severity:.0%}) | {period}{ack_badge}",
        expanded=(severity >= 0.7 and not acknowledged),
    ):
        left, right = st.columns(2)
        with left:
            st.metric("Observed", anomaly.get("observed_value", "—"))
            st.metric(
                "Expected Range",
                f"{anomaly.get('expected_low', '—')} – "
                f"{anomaly.get('expected_high', '—')}",
            )
        with right:
            st.metric("Detector", anomaly.get("detector_name", "—"))
            st.metric("Entity", anomaly.get("entity", "—"))

        if anomaly.get("llm_narrative"):
            st.info(anomaly["llm_narrative"])
        else:
            st.caption("LLM narrative pending…")

        if not acknowledged:
            anomaly_id = anomaly.get("id")
            if st.button("Acknowledge", key=f"ack_{anomaly_id}"):
                try:
                    resp = httpx.post(
                        f"{API_BASE}/api/anomalies/{anomaly_id}/acknowledge",
                        timeout=10,
                    )
                    resp.raise_for_status()
                    st.success("Acknowledged.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed: {exc}")
