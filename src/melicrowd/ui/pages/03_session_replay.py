"""Página: Session Replay — timeline horizontal de uma sessão."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from melicrowd.ui._client import get_session_replay, get_sessions

st.set_page_config(page_title="Session Replay", layout="wide")
st.title(":rewind: Session Replay")

# ---- Picker ----
recent = get_sessions(limit=50) or []
options = [f"{s.get('session_id')[:8]}… — {s.get('outcome')}  ({s.get('ended_at')})" for s in recent]
session_ids = [s.get("session_id") for s in recent]

if not options:
    st.info("Nenhuma sessão finalizada ainda. Rode `make start AGENTS=10` e aguarde alguns minutos.")
    st.stop()

idx = st.selectbox("Sessão", options=range(len(options)), format_func=lambda i: options[i])
session_id = session_ids[idx]

replay = get_session_replay(session_id)
if replay is None:
    st.error(f"Não consegui carregar replay de {session_id}")
    st.stop()

summary = replay["summary"]
steps = replay["steps"]

# ---- Summary ----
st.markdown("### Resumo")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Outcome", summary["outcome"])
c2.metric("Intent", summary.get("session_intent", "n/a"))
c3.metric("Total compra (R$)", f"{float(summary['purchase_total_brl']):.2f}")
c4.metric("Duração (s)", summary["duration_seconds"])

c5, c6, c7 = st.columns(3)
c5.metric("Qwen calls", summary["qwen_calls_count"])
c6.metric("Melisim calls", summary["melisim_calls_count"])
c7.metric("Persona ID", summary["persona_id"][:8] + "…")

# ---- Timeline ----
st.markdown("### Timeline de decisões")
if steps:
    df = pd.DataFrame(steps)
    df_show = df[["node", "latency_ms", "fallback_used", "error", "timestamp"]]
    st.dataframe(df_show, use_container_width=True, hide_index=True)

    st.markdown("### Detalhe por nó")
    for s in steps:
        emoji = ":robot:" if not s.get("fallback_used") else ":wrench:"
        with st.expander(f"{emoji} {s['node']} — {s['latency_ms']}ms" + (" (FALLBACK)" if s.get("fallback_used") else "")):
            st.json(s.get("response_parsed") or {})
            if s.get("error"):
                st.error(s["error"])
else:
    st.info("Sessão sem decisões Qwen registradas.")
