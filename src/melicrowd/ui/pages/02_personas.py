"""Página: Personas — browser com filtros e distribuições."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from melicrowd.ui._client import get_personas, post_personas_generate

st.set_page_config(page_title="Personas", layout="wide")
st.title(":bust_in_silhouette: Personas")

# ---- Generate ----
with st.expander("Gerar mais personas", expanded=False):
    count = st.number_input("Quantas?", min_value=1, max_value=2000, value=200, step=50)
    if st.button("Gerar via Qwen"):
        with st.spinner(f"gerando {count} personas via Qwen (pode demorar minutos)..."):
            result = post_personas_generate(int(count))
        st.toast(f"resultado: {result}")

# ---- Filters ----
col1, col2, col3 = st.columns(3)
income_class = col1.selectbox("Classe", options=["", "A", "B", "C", "D"])
state = col2.selectbox(
    "UF",
    options=["", "SP", "RJ", "MG", "RS", "PR", "BA", "PE", "CE", "GO", "DF"],
)
limit = col3.slider("Limit", min_value=10, max_value=500, value=50, step=10)

result = get_personas(
    limit=limit,
    income_class=income_class or None,
    location_state=state or None,
)
if result is None:
    st.warning("API indisponível.")
    st.stop()

items = result.get("items", [])
total = result.get("total", 0)
st.caption(f"Mostrando {len(items)} de {total} personas no DB.")

if items:
    df = pd.DataFrame(items)
    show_cols = [
        "name", "age", "gender", "income_class", "location_state", "location_city",
        "occupation", "price_sensitivity", "abandonment_likelihood", "review_likelihood",
    ]
    available = [c for c in show_cols if c in df.columns]
    st.dataframe(df[available], use_container_width=True, hide_index=True)

    st.markdown("### Distribuições")
    c1, c2, c3 = st.columns(3)
    if "income_class" in df.columns:
        c1.bar_chart(df["income_class"].value_counts())
    if "location_state" in df.columns:
        c2.bar_chart(df["location_state"].value_counts())
    if "age" in df.columns:
        c3.bar_chart(pd.cut(df["age"], bins=[18, 30, 45, 60, 85]).value_counts().sort_index())
else:
    st.info("Nenhuma persona ainda. Use Gerar acima ou rode `make seed-personas COUNT=200`.")
