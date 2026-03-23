"""
Streamlit application entry point — page router only.

Run: streamlit run kpi_lens/dashboard/app.py

This file has one responsibility: configure Streamlit and register pages.
No business logic, no direct DB calls, no chart rendering here.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="KPI-Lens | Supply Chain Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/aliivaezii/kpi-lens",
        "Report a bug": "https://github.com/aliivaezii/kpi-lens/issues",
        "About": "KPI-Lens — LLM-powered supply chain anomaly detection. "
        "Built by Ali Vaezi · github.com/aliivaezii",
    },
)

# Sidebar branding
with st.sidebar:
    st.markdown("## 📊 KPI-Lens")
    st.markdown("*Supply Chain Intelligence*")
    st.divider()

pages = [
    st.Page("pages/01_overview.py", title="Command Center", icon="🏠"),
    st.Page("pages/02_kpi_deep_dive.py", title="KPI Explorer", icon="📈"),
    st.Page("pages/03_anomaly_log.py", title="Anomaly Log", icon="⚠️"),
    st.Page("pages/04_llm_analyst.py", title="Ask the Analyst", icon="🤖"),
    st.Page("pages/05_reports.py", title="Reports", icon="📄"),
]

pg = st.navigation(pages)
pg.run()
