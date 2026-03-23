"""
Ask the Analyst — interactive LLM chat interface for supply chain Q&A.

Claude responds through the API (not direct SDK calls from Streamlit) so:
  - API credentials stay server-side
  - Streamlit reruns don't interrupt in-flight API calls
  - The same chat endpoint can be used by other frontends
"""

from __future__ import annotations

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.title("🤖 Ask the Analyst")
st.caption("Ask Claude anything about your supply chain KPIs")

# Suggested questions — surface the most common analyst workflows
SUGGESTED = [
    "Which KPI needs my attention most urgently this week?",
    "Why is OTIF declining? Walk me through the data.",
    "Which supplier is driving the DPPM anomaly?",
    "What will happen to inventory if lead time variance stays elevated?",
    "Generate a 3-bullet executive summary for today.",
]

with st.expander("💡 Suggested questions"):
    for q in SUGGESTED:
        if st.button(q, key=f"suggestion_{q[:20]}"):
            st.session_state.messages = st.session_state.get("messages", [])
            st.session_state.pending_message = q

# ── Chat history ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Input ─────────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask about your KPIs…")
pending = st.session_state.pop("pending_message", None)
prompt = pending or user_input

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analysing supply chain data…"):
            try:
                resp = httpx.post(
                    f"{API_BASE}/api/llm/chat",
                    json={"message": prompt, "history": st.session_state.messages[:-1]},
                    timeout=60,
                )
                resp.raise_for_status()
                reply = resp.json()["response"]
            except Exception as exc:
                reply = f"⚠️ Could not reach the analyst API: {exc}"
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.divider()
    if st.button("🗑 Clear conversation"):
        st.session_state.messages = []
        st.rerun()
