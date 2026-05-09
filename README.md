# MeliCrowd

> Simulador multi-agente de tráfego realista para o **Melisim** (e-commerce simulado).
> 50 agentes autônomos paralelos modulados por personas Qwen, navegando, comprando, abandonando
> carrinhos e gerando telemetria enriquecida para o data lake **MeliSimLake**.

| Campo            | Valor                                                 |
|------------------|-------------------------------------------------------|
| Status           | ✅ MVP completo (Fases 0-10)                          |
| Linguagem        | Python 3.11                                           |
| Frameworks       | LangGraph, FastAPI, Streamlit, asyncio (uvloop)       |
| LLM              | Qwen 3 14B via Ollama local                           |
| Persistência     | PostgreSQL 16 + Redis 7.4                             |
| Observabilidade  | Prometheus + Grafana (3 dashboards) + decision trace  |
| Cobertura        | ≥ 75% (target Fase 9)                                 |

---

## Quickstart

> Pré-requisitos: Docker Desktop, MeliSim e melisimlake já com `make up` rodado
> (precisamos das redes externas `melisim_melisim` e `melisimlake-net`),
> Ollama com `qwen3:14b` baixado.

```bash
cp .env.example .env          # ajuste se necessário
make up                       # sobe postgres + redis + prometheus + api + ui + orchestrator
make migrate                  # aplica schema Alembic
make ports                    # mostra URLs de cada UI
make seed-personas COUNT=200  # gera 200 personas via Qwen
make start AGENTS=50          # inicia 50 agentes paralelos
```

UIs:

- **Streamlit** — http://localhost:8502 (live agents, replay, métricas, load test)
- **API Swagger** — http://localhost:8101/docs (start/stop/scale, sessions, personas)
- **Prometheus** — http://localhost:9091

Demo end-to-end (sobe 3 sistemas, gera personas, roda 50 agentes por 15min):

```bash
bash scripts/demo.sh
```

---

## Ecosistema

```
~/python_projects/
├── MeliSim/        ← microsserviços (e-commerce simulado, 8 services em 4 linguagens)
├── melisimlake/    ← lakehouse + ML + ingestão
└── MeliCrowd/      ← este projeto (alimenta os dois)
```

Os 3 sistemas compartilham redes Docker. MeliCrowd:

- **chama** o api-gateway do MeliSim via REST (auth, products, orders, payments)
- **publica** eventos enriquecidos no Kafka do melisimlake (`events.simulator.*`)
- **roda** Qwen no Ollama do host

---

## Arquitetura

Veja **[ARCHITECTURE.md](ARCHITECTURE.md)** para o desenho completo.

```
┌──────────────────────────────────────────────────────────────────────┐
│  CONTROL PLANE  (FastAPI :8101 + Streamlit :8502 + CLI Typer)        │
├──────────────────────────────────────────────────────────────────────┤
│  ORCHESTRATOR   (asyncio + uvloop, pool de 50 workers)               │
├──────────────────────────────────────────────────────────────────────┤
│  AGENT          (LangGraph state machine + Redis checkpointer)       │
├──────────────────────────────────────────────────────────────────────┤
│  DECISION LAYER (Qwen sparse: 4 chamadas/sessão, semaphore=4)        │
├──────────────────────────────────────────────────────────────────────┤
│  EXECUTION LAYER (Markov + httpx + timing realista + error injection)│
│                  (token bucket → 100 req/min ao Melisim)             │
├──────────────────────────────────────────────────────────────────────┤
│  PERSISTENCE    (Postgres: histórico + Redis: estado live + TTL 1h)  │
├──────────────────────────────────────────────────────────────────────┤
│  OBSERVABILITY  (Prometheus + 3 dashboards Grafana + decision trace) │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Documentação

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — decisões de design, diagramas, trade-offs.
- **[RUNBOOK.md](RUNBOOK.md)** — troubleshooting, recovery, tuning (10+ cenários).
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — convenções de código, fluxo de PR.
- **[RECON.md](RECON.md)** — reconhecimento dos sistemas vizinhos.
- **[docs/blog_post.md](docs/blog_post.md)** — artigo Medium/dev.to (~2000 palavras).

---

## Comandos úteis

```bash
make help              # lista todos os targets
make ps                # status dos containers
make logs              # logs em tempo real
make logs-orchestrator # logs do pool de agentes
make status            # health checks
make dns-check         # confirma resolução DNS de melisim-api-gateway e kafka

make personas COUNT=200    # gera personas
make start AGENTS=50       # inicia pool
make scale AGENTS=100      # redimensiona em runtime
make stop                  # graceful shutdown

make lint              # ruff
make typecheck         # mypy strict
make test              # testes unitários
make test-integration  # testcontainers (Postgres, Redis)
make test-e2e          # 50 agentes, demo end-to-end
make coverage-html     # relatório HTML de cobertura
```

---

## Métricas alvo (calibradas com benchmarks BR)

Ao rodar 50 agentes por 1h+:

| Métrica | Real (BR 2024-25) | Alvo MeliCrowd |
|---|---|---|
| Conversion rate | 2-5% | 3% |
| Cart abandonment | 60-80% | 70% |
| Avg session duration | 6-10min | 8min |
| Avg order value | R$ 380 | R$ 400 |
| Sessões/hora | — | ≥ 100 |

Acompanhe ao vivo em http://localhost:8502 (página **Metrics**) e
http://localhost:9091.

---

## Roadmap das fases (concluído)

| Fase | Conteúdo                                      | Status |
|------|-----------------------------------------------|--------|
| 0    | RECON dos vizinhos                            | ✅     |
| 1    | Infraestrutura local                          | ✅     |
| 2    | Camada Persona (Qwen)                         | ✅     |
| 3    | Agent LangGraph state machine                 | ✅     |
| 4    | Camada de execução procedural (Markov+HTTP)   | ✅     |
| 5    | Orchestrator (pool de 50 agentes)             | ✅     |
| 6    | Control plane FastAPI                         | ✅     |
| 7    | Observabilidade (Prometheus + Grafana)        | ✅     |
| 8    | UI Streamlit (5 páginas)                      | ✅     |
| 9    | Testes (unit + integration + e2e)             | ✅     |
| 10   | Documentação + demo + blog post               | ✅     |

---

## Licença

MIT.
