"""Página: Load Test — instrui rodar locust externamente.

Embutir locust dentro do Streamlit é fragil (locust gerencia seu próprio
event loop). Em vez disso, fornecemos comando pronto + visualização do
locustfile já preparado em ``infra/locust/``.
"""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Load Test", layout="wide")
st.title(":hammer_and_wrench: Load Test (locust)")

st.markdown(
    """
    Como rodar load test contra o **Melisim** usando os mesmos endpoints que os agentes:

    ```bash
    cd MeliCrowd
    poetry run locust -f infra/locust/melisim_load.py \\
      --host=http://localhost:18000 \\
      --users=200 --spawn-rate=10 --run-time=10m
    ```

    Abra http://localhost:8089 para a UI do locust.

    Os scripts em `infra/locust/` exercitam:
    - `/api/v1/auth/register`
    - `/api/v1/products/search?q=`
    - `/api/v1/products/{id}`
    - `/api/v1/orders` + `/api/v1/payments`
    """
)

st.markdown("### Recomendações")
st.markdown(
    """
    - **Não rode load test enquanto o pool de agentes está ativo** — eles
      compartilham rate limit do gateway (100 req/min).
    - **Aumente RPS gradualmente** — Melisim tem outbox + Resilience4j; pode
      degradar antes de quebrar.
    - **Compare métricas** com os dashboards Grafana do Melisim (porta 13000).
    """
)
