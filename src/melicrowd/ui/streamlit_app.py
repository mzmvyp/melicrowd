"""MeliCrowd — entrypoint do Streamlit (multi-page).

Streamlit descobre páginas em ``ui/pages/`` automaticamente.
Esta página inicial mostra status global e atalhos.
"""
from __future__ import annotations

import streamlit as st

from melicrowd import __version__
from melicrowd.ui._client import get_status

st.set_page_config(
    page_title="MeliCrowd — Simulador Multi-Agente",
    page_icon=":bar_chart:",
    layout="wide",
)

st.title(":bar_chart: MeliCrowd")
st.caption(f"versão {__version__} — simulador multi-agente para o Melisim")

status = get_status()
if status is None:
    st.warning("API não disponível em http://api:8101 — verifique `make ps`.")
else:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Agentes ativos", status.get("pool", {}).get("active_agents", 0))
    col2.metric("Target", status.get("pool", {}).get("target_agents", 0))
    col3.metric("Pool rodando?", "sim" if status.get("pool", {}).get("running") else "não")
    col4.metric("Qwen modelo", status.get("config", {}).get("qwen_model", "?"))

st.markdown("---")
st.markdown(
    """
    ### Páginas disponíveis (sidebar)

    - **Live Agents** — tabela atualizada a cada 2s.
    - **Personas** — browser com filtros e distribuições.
    - **Session Replay** — timeline de uma sessão por ID.
    - **Metrics** — KPIs vs benchmarks reais.
    - **Load Test** — locust embedded.

    ### Comandos rápidos
    """
)

with st.expander("Como controlar o pool", expanded=False):
    st.code(
        """
# CLI
make seed-personas COUNT=200
make start AGENTS=50
make stop
make scale AGENTS=100

# API
curl -X POST http://localhost:8101/start?agents=50
curl http://localhost:8101/status
""".strip()
    )
