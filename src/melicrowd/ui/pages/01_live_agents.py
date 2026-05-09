"""Página: Live Agents — tabela atualizada periodicamente."""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from melicrowd.ui._client import get_agents, get_pool_status, post_scale, post_start, post_stop

st.set_page_config(page_title="Live Agents", layout="wide")
st.title(":runner: Live Agents")

# ---- Controls ----
ctrl = st.container()
with ctrl:
    c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
    target = c1.number_input("Target agents", min_value=1, max_value=500, value=50, step=10)
    if c2.button("Start"):
        result = post_start(target)
        st.toast(f"start: {result}")
    if c3.button("Stop"):
        result = post_stop(graceful=True)
        st.toast(f"stop: {result}")
    if c4.button("Resize"):
        result = post_scale(target)
        st.toast(f"scale: {result}")

placeholder = st.empty()
refresh_seconds = st.sidebar.slider("Refresh (s)", min_value=1, max_value=10, value=2)
auto_refresh = st.sidebar.toggle("Auto-refresh", value=True)


def _render() -> None:
    pool = get_pool_status() or {}
    agents = get_agents() or {}

    with placeholder.container():
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Active", pool.get("active_agents", 0))
        col2.metric("Target", pool.get("target_agents", 0))
        col3.metric("Qwen in_flight", pool.get("qwen_in_flight", 0))
        col4.metric("Qwen waiting", pool.get("qwen_waiting", 0))

        workers = agents.get("workers", [])
        if workers:
            df = pd.DataFrame(workers)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Pool sem workers ativos. Use Start acima.")


_render()
if auto_refresh:
    time.sleep(refresh_seconds)
    st.rerun()
