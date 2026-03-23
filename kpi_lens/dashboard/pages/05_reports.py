"""
Reports — trigger on-demand anomaly reports and view the report log.

Report generation is asynchronous: this page enqueues the job via the API
and the background scheduler executes it. The report log shows generated reports.
"""

from __future__ import annotations

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.title("📄 Reports")
st.caption("Generate and download supply chain anomaly reports")

# ── Report trigger ─────────────────────────────────────────────────────────────
st.subheader("Generate Report")

with st.form("report_form"):
    recipients = st.text_input(
        "Recipients (comma-separated emails)",
        placeholder="analyst@company.com, manager@company.com",
    )
    days_back = st.slider("Cover anomalies from last N days", 7, 90, 30)
    severity_floor = st.slider("Minimum severity to include", 0.0, 1.0, 0.5, 0.05)
    submitted = st.form_submit_button("📤 Enqueue Report")

if submitted:
    if not recipients.strip():
        st.warning("Please enter at least one recipient email.")
    else:
        # First fetch the anomalies to get their IDs
        try:
            anomaly_resp = httpx.get(
                f"{API_BASE}/api/anomalies",
                params={"days_back": days_back, "severity_floor": severity_floor},
                timeout=10,
            )
            anomaly_resp.raise_for_status()
            anomalies = anomaly_resp.json()
            anomaly_ids = [a["id"] for a in anomalies if "id" in a]

            if not anomaly_ids:
                st.warning(
                    "No anomalies found for the selected filters — nothing to report."
                )
            else:
                enqueue_resp = httpx.post(
                    f"{API_BASE}/api/reports/enqueue",
                    json={
                        "anomaly_ids": anomaly_ids,
                        "recipients": [r.strip() for r in recipients.split(",")],
                        "triggered_by": "dashboard",
                    },
                    timeout=10,
                )
                enqueue_resp.raise_for_status()
                job_data = enqueue_resp.json()
                st.success(f"Report enqueued — job ID: `{job_data.get('job_id')}`")
                st.caption(
                    f"Covers {len(anomaly_ids)} anomalies for "
                    f"{len(recipients.split(','))} recipient(s)."
                )
        except Exception as exc:
            st.error(f"Failed to enqueue report: {exc}")

st.divider()

# ── Report log ─────────────────────────────────────────────────────────────────
st.subheader("Report Log")
st.caption("Recent report generation history (Phase 3 — coming soon)")
st.info(
    "Full report generation (Excel + PowerPoint) is implemented in Phase 3. "
    "The report log will appear here once the first report is generated."
)

with st.sidebar:
    st.divider()
    if st.button("🔄 Refresh"):
        st.rerun()
