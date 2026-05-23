# Arquitetura — MeliCrowd

Este documento descreve as decisões de design do MeliCrowd: as camadas, como os
três tipos de agente coexistem, os trade-offs explícitos e os pontos de
integração com os sistemas vizinhos.

## Sumário

- [Princípios](#princípios)
- [Visão de camadas](#visão-de-camadas)
- [Os três agentes](#os-três-agentes)
- [Fluxo do Live Floor (tempo real)](#fluxo-do-live-floor-tempo-real)
- [Stack tecnológico](#stack-tecnológico)
- [Integração com vizinhos](#integração-com-vizinhos)
- [Trade-offs explícitos](#trade-offs-explícitos)
- [Diretório](#diretório)

---

## Princípios

1. **Sparse LLM** — chamadas a LLM são caras (latência + GPU/USD). O LLM atua
   apenas nas decisões macro (4 por sessão de buyer); tudo entre elas é Markov
   procedural barata e determinística.
2. **Fallback sempre** — todo nó que usa LLM tem um caminho procedural de
   contingência baseado nos atributos da persona. Timeout ou JSON inválido no
   Qwen nunca trava uma sessão.
3. **Realismo > throughput** — as taxas de conversão e abandono devem bater os
   benchmarks reais do varejo BR (2–5 % / 60–80 %). Métrica que destoa do real
   denuncia simulação artificial.
4. **Observabilidade nativa** — toda decisão de LLM é auditável (prompt +
   resposta + latência + flag de fallback no Postgres); toda métrica relevante
   vai para o Prometheus; o estado vivo é transmitido por WebSocket.
5. **Graceful shutdown** — `SIGTERM` dispara *drain*: sessões em andamento
   terminam ou rolam o checkpoint para o Redis para *recovery*.
6. **Async em tudo** — o workload é I/O-bound (HTTP + LLM + Kafka + DB).
   `asyncio` + `uvloop` cobrem; threads/multiprocessing não trariam ganho.
7. **Pydantic em todos os boundaries** — dados que cruzam fronteira (HTTP,
   Kafka, DB, saída de LLM) são validados na entrada; o núcleo confia nos tipos.
8. **Não modificar os vizinhos** — MeliCrowd se integra ao MeliSim e ao data
   lake sem alterá-los; restrições (como rate limit) são absorvidas internamente.

## Visão de camadas

| Camada | Responsabilidade | Latência alvo |
|---|---|---|
| **Presentation** | Live Floor / Topology / Tasks (React + nginx, :8503) consumindo `ws://api/ws/agents` | snapshot 5 Hz |
| **Control plane** | start/stop/scale, inspeção, replay, geração de tasks (FastAPI :8101, Streamlit :8502, CLI) | < 100 ms |
| **Orchestration** | ciclo de vida de N buyers + M sellers + serviço Tech Lead; signal handling | tick 1 s |
| **Agents** | buyer (LangGraph, estado + checkpoint) · seller (loop procedural) · tech lead (loop DeepSeek) | tick 100 ms |
| **Decision** | Qwen 3 14B (4 calls/sessão buyer, 3/sessão seller) · DeepSeek V4 Pro (tech lead) | 2–15 s p95 |
| **Execution** | Markov + HTTP (httpx) + timing humano + error injection; token bucket | 100 ms–30 s |
| **Persistence** | Redis (estado vivo, checkpoint, TTL) + Postgres (histórico, tasks) | < 50 ms |
| **Observability** | Prometheus + LiveAgentTracker + decision trace | passivo |

## Os três agentes

O MeliCrowd modela um marketplace vivo com três populações de agentes. Cada uma
usa o motor de decisão mais adequado à sua complexidade.

### Buyer — LangGraph state machine

Compradores são o caso mais complexo (ramificações reais: comparar, voltar à
lista, abandonar, pagar), então usam uma **máquina de estado LangGraph** com 14
nós e 5 arestas condicionais. O estado é um modelo Pydantic; o checkpointer
Redis (TTL 1 h) habilita replay determinístico e recovery.

As 4 chamadas Qwen por sessão: `decide_session` (intenção + orçamento),
`evaluate_item` (adicionar ao carrinho?), `checkout_decision` (pagar ou
abandonar?) e `write_review` (opcional, pós-compra). Os outros 10 nós são
procedurais.

### Seller — loop procedural

Vendedores não têm ramificação suficiente para justificar um grafo: rodam um
loop procedural de ciclos curtos (~30 s–2 min) com folga de 5–30 min entre eles.
Cada ciclo executa um subconjunto de ações: `audit_inventory`,
`check_notifications` (alertas de estoque baixo), `restock`
(`PATCH /products/{id}/stock`), `suspend`, `create_product` e `update_price`.
Qwen entra em 3 pontos: foco da sessão, avaliação de cada notificação e geração
do texto livre de produtos novos.

> O `restock` é exatamente o tipo de escrita assíncrona, sujeita a *retry*, que
> torna a idempotência do endpoint de estoque do MeliSim relevante: vários
> sellers podem reaplicar o mesmo delta sob retransmissão.

### Tech Lead — melhoria contínua dirigida por IA

Um agente operacional que usa **DeepSeek V4 Pro** (reasoning model, cloud) para
transformar itens de um *backlog blueprint* em tarefas técnicas ricas com
**critérios de aceite verificáveis por máquina**. O diferencial de design é a
**avaliação objetiva**: em vez de o LLM "achar" que a tarefa está pronta, um
*evaluator* roda checks concretos (tabela existe no Postgres? endpoint no
OpenAPI? métrica no Prometheus? commit casa o padrão? pytest verde?) e só fecha
a tarefa quando 100 % passam. Custo de geração/avaliação é rastreado em USD por
tarefa. Ver **[docs/tech-lead-agent.md](docs/tech-lead-agent.md)**.

## Fluxo do Live Floor (tempo real)

```
Agent.run_session()
  └─ graph.astream(stream_mode="updates")        ← cada nó executado
       └─ tracker.upsert_from_state(state, station_override=node_name)
            └─ asyncio.Lock → atualiza dict in-memory
                 └─ /ws/agents tick (200 ms / 5 Hz)
                      └─ tracker.snapshot() → JSON {agents, events, kpis}
                           └─ broadcast a todos os clientes WebSocket
                                └─ React atualiza o estado
                                     └─ AgentDot reposiciona na estação
```

A LangGraph emite um update por nó visitado (15–20/sessão). Cada nó é embrulhado
por um *wrapper* que atualiza o tracker **antes** de o nó executar — sem isso,
nós lentos (Qwen, 2–6 s) fariam o agente parecer "travado" na estação anterior.
O `/ws/agents` faz tick a 5 Hz independentemente da quantidade de agentes e
envia o snapshot completo; o frontend desenha por *diff*, o que o torna
tolerante a reconexão e estável em cardinalidade.

## Stack tecnológico

Versões pinadas em `pyproject.toml`. Destaques:

- **Python 3.11** + **uvloop** — event loop async de alta performance.
- **LangGraph 0.2.x** — state machine + checkpointers plugáveis.
- **LLM:** **Qwen 3 14B** via **Ollama** (local) e **DeepSeek V4 Pro** (cloud,
  API OpenAI-compatible, usado pelo Tech Lead).
- **httpx 0.28** (HTTP async) + **aiokafka 0.12** + **tenacity 9** (retry).
- **PostgreSQL 16** + **asyncpg** + **SQLAlchemy 2.x async** + **Alembic**.
- **Redis 7.4** com AOF + keyspace events (checkpointer + estado vivo).
- **FastAPI 0.115** + **Streamlit 1.41** + **Typer**.
- **Prometheus** + **Grafana** (dashboards provisionados) + **OpenTelemetry**
  (opcional).
- **React** zero-build (CDN + Babel standalone) servido por **nginx**.

## Integração com vizinhos

### MeliSim (consumidor REST)

- Hostname interno: `melisim-api-gateway:8000` (rede `melisim_melisim`).
- Endpoints usados: `/api/v1/auth/{register,login}`, `/api/v1/products`,
  `/api/v1/products/search`, `/api/v1/products/{id}`, `/api/v1/orders`,
  `/api/v1/orders/{id}`, `/api/v1/payments` (com `Idempotency-Key`) e
  `/api/v1/products/{id}/stock` (restock dos sellers).
- Endpoints ausentes que o agente contorna:
  - `cart/items` — o carrinho do buyer vive em memória no `AgentState`.
  - `reviews` — review vira evento Kafka, não chamada REST.

### Data lake (publisher Kafka)

- Bootstrap: `kafka:9092` (rede `melisimlake-net`); Schema Registry em
  `http://schema-registry:8081`.
- Tópicos publicados: `events.simulator.session_started`,
  `events.simulator.decision_made`, `events.simulator.session_ended`.
- **Degradação graciosa:** se o broker está indisponível, o publisher entra em
  modo *degraded* (no-op silencioso, log único) — o pool de agentes não falha
  por causa de um consumidor opcional.

### Qwen / Ollama (LLM local)

- Endpoint: `http://host.docker.internal:11434`; modelo `qwen3:14b`.
- Pool semaphore: máximo de 12 chamadas concorrentes — tune via
  `MELICROWD_QWEN_MAX_CONCURRENT`. Acima disso, o p99 do Ollama 14B degrada.

### DeepSeek V4 Pro (LLM cloud)

- API OpenAI-compatible, usada exclusivamente pelo Tech Lead Agent.
- Custo por chamada rastreado e persistido por tarefa (input/output/cache).

## Trade-offs explícitos

| Escolha | Alternativa rejeitada | Por quê |
|---|---|---|
| Buyer em LangGraph | LangChain `AgentExecutor` | Replay + checkpointer + roteamento tipado |
| Seller em loop procedural | LangGraph para todos | Sem ramificação que justifique o overhead de um grafo |
| Tech Lead com avaliação objetiva | LLM julgando a própria entrega | Evita alucinação/drift; critério verificável é auditável |
| Qwen local p/ buyers/sellers, DeepSeek p/ tech lead | Tudo num LLM só | Qwen local satura com 50 agentes; tech lead exige reasoning longo |
| Pool buyers=50, Qwen semaphore=12 | 50 chamadas Qwen paralelas | Saturaria o Ollama 14B; p99 explode |
| Redis p/ estado vivo, Postgres só p/ finalizado | Postgres em todo tick | TTL automático, latência menor |
| Token bucket interno (rate limit) | Modificar o gateway do MeliSim | Não modificar projeto vizinho |
| Prometheus standalone | Federação com o data lake | Menos acoplamento |
| Async + asyncio | Threads / multiprocessing | Workload I/O-bound |
| `events.simulator.*` namespace | Reusar tópicos do data lake | Telemetria do simulador isolada |
| WebSocket snapshot 5 Hz | Push por evento individual | Frontend desenha por diff; tolerante a reconexão |
| LiveAgentTracker in-memory | Redis pub/sub cross-process | Pool e API no mesmo processo — evita serialização |
| Frontend zero-build (CDN) | Vite/Webpack | Clonar e abrir sem `npm install`; em produção usar-se-ia Vite |

## Diretório

```
melicrowd/
├── src/melicrowd/
│   ├── config.py            # pydantic-settings (fonte única de verdade)
│   ├── logging_setup.py     # loguru + intercept da stdlib
│   ├── personas/            # geração/persistência de personas (buyer)
│   ├── agents/              # buyer: grafo LangGraph (nodes/, prompts/, edges)
│   ├── sellers/             # seller: loop procedural (actions/, prompts/)
│   ├── tech_lead/           # Tech Lead Agent (DeepSeek): generator, evaluator, backlog
│   ├── execution/           # Markov + HTTP + timing + Kafka + rate limiter
│   ├── llm/                 # cliente Qwen/Ollama, pool semaphore, trace
│   ├── orchestrator/        # AgentPool, SellerPool, schedulers, lifecycle
│   ├── api/                 # FastAPI: routers + schemas
│   ├── observability/       # Prometheus + LiveAgentTracker
│   ├── ui/                  # Streamlit
│   └── cli.py               # Typer
├── frontend/                # React zero-build: index (Live Floor), topology, tasks
├── infra/
│   ├── postgres/init.sql + migrations/   # 0001 schema · 0002 sellers · 0003 tech_lead
│   ├── redis/redis.conf
│   ├── prometheus/prometheus.yml
│   ├── grafana/dashboards/
│   └── nginx/               # config do frontend
├── tests/{unit,integration,e2e}/
├── docker-compose.yml + Dockerfile
└── Makefile
```
