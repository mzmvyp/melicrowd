"""Página: Metrics — KPIs vs benchmarks reais de e-commerce BR."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from melicrowd.ui._client import get_sessions

st.set_page_config(page_title="Metrics", layout="wide")
st.title(":chart_with_upwards_trend: Metrics & Benchmarks")


def _status(value: float, lo: float, hi: float) -> str:
    if value < lo:
        return f"abaixo do realista ({lo:.0%})"
    if value > hi:
        return f"acima do realista ({hi:.0%})"
    return "dentro do realista"


# ---- Benchmarks reais (públicos, e-commerce BR) ----
BENCHMARKS = {
    "conversion_rate_min": 0.02,
    "conversion_rate_max": 0.05,
    "abandonment_rate_min": 0.60,
    "abandonment_rate_max": 0.80,
    "avg_order_value_brl": 380.0,
    "avg_session_duration_min": 7.5,
}

st.caption(
    "Comparação com benchmarks reais do e-commerce brasileiro "
    "(Mercado Livre / Magalu / Amazon BR — dados públicos 2024-2025)."
)

sessions = get_sessions(limit=500) or []
if not sessions:
    st.info("Sem sessões finalizadas ainda.")
    st.stop()

df = pd.DataFrame(sessions)

# ---- KPIs ----
total = len(df)
purchased = (df["outcome"] == "purchased").sum()
abandoned = (df["outcome"] == "abandoned_cart").sum()
conversion = purchased / total if total > 0 else 0
abandon_rate = abandoned / total if total > 0 else 0
aov = df.loc[df["outcome"] == "purchased", "purchase_total_brl"].astype(float).mean() if purchased > 0 else 0
avg_dur = df["duration_seconds"].mean() / 60.0 if total > 0 else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Conversion rate",
    f"{conversion:.1%}",
    delta=_status(conversion, BENCHMARKS["conversion_rate_min"], BENCHMARKS["conversion_rate_max"]),
    help="Real BR: 2-5%",
) if total > 0 else col1.metric("Conversion rate", "—")

col2.metric(
    "Cart abandonment",
    f"{abandon_rate:.1%}",
    delta=_status(abandon_rate, BENCHMARKS["abandonment_rate_min"], BENCHMARKS["abandonment_rate_max"]),
    help="Real BR: 60-80%",
)

col3.metric("AOV (R$)", f"{aov:.2f}", help="Average order value")
col4.metric("Avg sessão (min)", f"{avg_dur:.1f}")

st.markdown("---")
st.markdown("### Outcomes (últimas 500 sessões)")
outcomes = df["outcome"].value_counts()
st.bar_chart(outcomes)

st.markdown("### Persona class × Outcome")
if "persona_id" in df.columns and "outcome" in df.columns:
    cross = df.groupby("outcome").size()
    st.dataframe(cross.to_frame("count"))
