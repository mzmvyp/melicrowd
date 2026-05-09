# Arquitetura — MeliCrowd

> Documento vivo. Será expandido no fim da Fase 10 com diagramas Mermaid
> auto-gerados, decisões de design completas e referências.

## Sumário

- [Princípios](#princípios)
- [Camadas](#camadas)
- [Stack tecnológico](#stack-tecnológico)
- [Integração com vizinhos](#integração-com-vizinhos)
- [Trade-offs explícitos](#trade-offs-explícitos)
- [Diretório](#diretório)

---

## Princípios

1. **Sparse LLM** — Qwen é caro. Chama apenas em decisões macro (4 por sessão).
   Tudo entre as decisões é Markov procedural barata.
2. **Realismo > performance** — taxas de conversão e abandono devem bater
   benchmarks reais de e-commerce BR (2-5% / 60-80%). Recrutador percebe se for fake.
3. **Observabilidade nativa** — toda decisão Qwen é auditável (prompt+resposta no Postgres).
   Toda métrica importante vai para Prometheus.
4. **Graceful** — SIGTERM faz drain. Sessões em flight terminam ou rolam pra Redis pra recovery.
5. **Async tudo** — workload é I/O bound (HTTP + LLM + Kafka). Threads não ajudariam; asyncio cobre.
6. **Pydantic em todos os boundaries** — validação no início, dados confiáveis depois.

## Camadas

| Camada           | Responsabilidade                                 | Latência alvo |
|------------------|--------------------------------------------------|---------------|
| Control plane    | Start/stop/scale, inspeção, replay               | < 100ms       |
| Orchestrator     | Lifecycle de N agentes, signal handling          | tick 1s       |
| Agent (LangGraph)| Estado, transições, checkpointing                | tick 100ms    |
| Decision (Qwen)  | 4 decisões/sessão (intent, item, checkout, review)| 2-15s p95    |
| Execution        | Markov + HTTP + timing + error injection         | 100ms-30s     |
| Persistence      | Redis (live) + Postgres (histórico)              | < 50ms        |
| Observability    | Prometheus + decision trace + Streamlit          | passive       |

## Stack tecnológico

Versões pinadas em `pyproject.toml`. Highlights:

- **Python 3.11** + **uvloop** (event loop performance)
- **LangGraph 0.2.x** (state machine + checkpointers)
- **httpx 0.28** (async HTTP) + **aiokafka 0.12** + **tenacity 9** (retry)
- **Postgres 16** + **asyncpg** + **SQLAlchemy 2.x async** + **Alembic**
- **Redis 7.4** com AOF + keyspace events
- **FastAPI 0.115** + **Streamlit 1.41** + **Typer**
- **Prometheus** + **OpenTelemetry** (opcional)

Detalhes na Fase 10.

## Integração com vizinhos

### MeliSim (consumidor REST)

- Hostname interno: `melisim-api-gateway:8000` (rede `melisim_melisim`)
- Endpoints usados: `/api/v1/auth/{register,login}`, `/api/v1/products`,
  `/api/v1/products/search`, `/api/v1/products/{id}`, `/api/v1/orders`,
  `/api/v1/orders/{id}`, `/api/v1/payments` (com `Idempotency-Key`).
- Endpoints **ausentes** que o agente lida sem chamar:
  - `cart/items` — carrinho fica em memória no `AgentState`.
  - `reviews` — review vira só evento Kafka.

### MeliSimLake (publisher Kafka)

- Bootstrap: `kafka:9092` (rede `melisimlake-net`)
- Schema Registry: `http://schema-registry:8081`
- Tópicos publicados:
  - `events.simulator.session_started`
  - `events.simulator.decision_made`
  - `events.simulator.session_ended`

### Qwen / Ollama

- Endpoint: `http://host.docker.internal:11434`
- Modelo: `qwen3:14b`
- Pool semaphore: max 4 chamadas concorrentes (preserva latência p99)

## Trade-offs explícitos

| Escolha                              | Alternativa rejeitada       | Por quê                                   |
|--------------------------------------|-----------------------------|-------------------------------------------|
| LangGraph                            | LangChain `AgentExecutor`   | LangGraph permite replay + checkpointer   |
| Pool=50 (CPU), Qwen pool=4           | 50 chamadas Qwen paralelas  | Saturaria o Ollama de 14B; p99 explode    |
| Redis para estado live, Postgres só pra finalizado | Postgres em todo tick | TTL automático, latência menor            |
| Token bucket interno (rate limit)    | Modificar gateway do MeliSim| Não modificar projeto vizinho             |
| Prometheus standalone                | Federação com melisimlake   | Acoplamento; standalone é simples         |
| Async + asyncio                      | Threads / multiprocessing   | Workload é I/O bound; threads não ajudam  |
| `events.simulator.*` namespace       | Reusar tópicos do melisimlake| Separação de telemetria do simulador     |

## Diretório

```
melicrowd/
├── src/melicrowd/
│   ├── config.py            # Pydantic Settings (única fonte de verdade)
│   ├── logging_setup.py     # loguru + intercept stdlib
│   ├── personas/            # Camada Persona (Fase 2)
│   ├── agents/              # LangGraph state machine (Fase 3)
│   ├── execution/           # Markov + HTTP + timing (Fase 4)
│   ├── llm/                 # Qwen client + pool (Fase 2-3)
│   ├── orchestrator/        # Pool de N agentes (Fase 5)
│   ├── api/                 # FastAPI control plane (Fase 6)
│   ├── ui/                  # Streamlit (Fase 8)
│   ├── observability/       # Prometheus + tracing (Fase 7)
│   └── cli.py               # Typer
├── infra/
│   ├── postgres/init.sql + migrations/
│   ├── redis/redis.conf
│   ├── prometheus/prometheus.yml
│   └── grafana/dashboards/  # Fase 7
├── tests/{unit,integration,e2e}/
├── docker-compose.yml + override.yml + Dockerfile
└── Makefile
```
