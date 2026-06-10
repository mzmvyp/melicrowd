# MeliCrowd

> **Plataforma multi-agente de simulação de tráfego para e-commerce.**
> Centenas de agentes autônomos — compradores, vendedores e um *tech lead* — operam em paralelo sobre um marketplace simulado, gerando comportamento humano realista, telemetria enriquecida e um ciclo de melhoria contínua dirigido por IA.

<p>
<img alt="Python" src="https://img.shields.io/badge/python-3.11-blue.svg">
<img alt="LangGraph" src="https://img.shields.io/badge/agents-LangGraph-7c3aed.svg">
<img alt="FastAPI" src="https://img.shields.io/badge/api-FastAPI-009688.svg">
<img alt="LLM" src="https://img.shields.io/badge/LLM-Qwen3%208B%20%2B%20DeepSeek%20V4-orange.svg">
<img alt="License" src="https://img.shields.io/badge/license-MIT-green.svg">
</p>

| | |
|---|---|
| **Linguagem** | Python 3.11 (async / `uvloop`) |
| **Orquestração de agentes** | LangGraph (state machine + checkpointer) |
| **LLMs** | Qwen 3 8B local (Ollama) · DeepSeek V4 Pro (cloud) |
| **Persistência** | PostgreSQL 16 · Redis 7.4 |
| **Mensageria** | Apache Kafka (telemetria → data lake) |
| **Observabilidade** | Prometheus · Grafana · WebSocket Live Floor · decision trace |
| **Control plane** | FastAPI · Streamlit · CLI (Typer) |

---

## O que é

MeliCrowd injeta **tráfego sintético de comportamento humano** num e-commerce de microsserviços (o sistema-alvo **MeliSim**). Em vez de disparar requisições uniformes como um teste de carga clássico, cada agente é uma entidade autônoma com **persona psicográfica** (idade, classe social, sensibilidade a preço, propensão ao abandono...) que **navega, pesquisa, compara, compra ou desiste** — e o conjunto de milhares de decisões individuais produz curvas agregadas realistas (conversão ~3%, abandono de carrinho ~70%), calibradas com benchmarks do varejo brasileiro.

O sistema cobre **três populações de agentes** que, juntas, formam um marketplace vivo e um ciclo de evolução contínua:

| Agente | Motor de decisão | Papel |
|---|---|---|
| 🛒 **Buyer** | LangGraph (14 nós, 2-9 chamadas Qwen/sessão) | Navega o catálogo, avalia produtos (score LLM × sorteio calibrado), abandona ou compra, escreve reviews |
| 🏪 **Seller** | Loop procedural (3 chamadas Qwen/sessão) | Audita inventário, repõe estoque, cria/precifica produtos, responde alertas |
| 🧑‍💼 **Tech Lead** | DeepSeek V4 Pro (cloud) | Gera tarefas técnicas de melhoria com critérios de aceite **objetivos**, avalia entregas automaticamente e fecha quando 100% dos checks passam |

### Que problema resolve

Gerar dados e carga realistas de e-commerce sem tráfego de produção (caro, lento, sujeito a LGPD), e ao mesmo tempo servir de **plataforma de experimentação para agentes de IA em produção** — com LLM sob restrições reais (latência, custo, *fallback*), orquestração assíncrona controlada e observabilidade auditável de cada decisão.

---

## Arquitetura

```
┌──────────────────────────────────────────────────────────────────────────┐
│  PRESENTATION   Live Floor (React :8503)  ◀─ ws://api/ws/agents (5 Hz) ─┐ │
│                 Topology NOC · Tasks Kanban (Tech Lead)                 │ │
├──────────────────────────────────────────────────────────────────────────┤
│  CONTROL PLANE  FastAPI :8101  ·  Streamlit :8502  ·  Typer CLI         │ │
│                 /start /stop /scale · /agents /sessions · /tasks ───────┘ │
├──────────────────────────────────────────────────────────────────────────┤
│  ORCHESTRATION  asyncio + uvloop                                          │
│                 AgentPool (buyers)  ·  SellerPool  ·  Tech Lead service   │
├──────────────────────────────────────────────────────────────────────────┤
│  AGENTS         Buyer = LangGraph (14 nós + Redis checkpointer)           │
│                 Seller = loop procedural   ·   Tech Lead = DeepSeek loop  │
├──────────────────────────────────────────────────────────────────────────┤
│  DECISION       Qwen 3 8B (Ollama, semaphore=8)    │  DeepSeek V4 Pro     │
│                 híbrido: LLM pontua, RNG sorteia    │  geração + avaliação │
├──────────────────────────────────────────────────────────────────────────┤
│  EXECUTION      sorteio calibrado + httpx + timing humano + error inject  │
│                 token bucket → respeita rate limit do MeliSim             │
├──────────────────────────────────────────────────────────────────────────┤
│  PERSISTENCE    PostgreSQL 16 (histórico + tasks)  ·  Redis 7.4 (live)    │
├──────────────────────────────────────────────────────────────────────────┤
│  OBSERVABILITY  Prometheus · Grafana · LiveAgentTracker · decision trace  │
├──────────────────────────────────────────────────────────────────────────┤
│  EXTERNAL       ── REST ─▶ MeliSim api-gateway (auth/products/orders)     │
│                 ── Kafka ─▶ data lake  (events.simulator.*)               │
│                 ◀── Ollama (local)  ·  DeepSeek API (cloud)               │
└──────────────────────────────────────────────────────────────────────────┘
```

**Princípio central — _o LLM pontua, o procedural sorteia_:** um LLM em temperatura baixa é um classificador ~determinístico — pedir a ele uma decisão binária produz taxa agregada "tudo-ou-nada" (medido: 0%, 90%, 0% em três calibrações de prompt), nunca os ~3-8% de conversão do varejo real. Por isso as decisões seguem o padrão híbrido: o Qwen devolve **juízo qualitativo contínuo** (intent da sessão, `interest_level` 0-1 por produto) e a **amostragem** fica num RNG procedural calibrado, modulado por persona + score do LLM (fator 0.4-1.6×, centrado em 1.0). A pacing entre nós usa **timing humano** (think time, digitação, scroll — `execution/timing.py`, escala configurável). Quando o LLM falha (timeout, JSON inválido), cada nó cai num **fallback neutro** que preserva a calibração: a sessão nunca trava e a taxa não desloca.

Detalhes de design, camadas e trade-offs em **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## Os três agentes

### 🛒 Buyer — máquina de estado LangGraph

Cada comprador percorre um grafo de **14 nós** (3 com Qwen por default — `decide_session`, `evaluate_item` híbrido e `write_review`; `checkout_decision` opcional — o restante procedural) com 5 arestas condicionais:

```
load_persona → decide_session ─┬─▶ auth → browse_home → search → product_list
                               │        → product_detail → evaluate_item ─┬─▶ add_to_cart
                               └─▶ abandon                                 ├─▶ back_to_list
                                                                           └─▶ abandon
add_to_cart → continue_or_checkout ─┬─▶ search (continua)
                                    └─▶ checkout_decision ─┬─▶ pay → write_review → END
                                                           └─▶ abandon → END
```

Estado tipado em Pydantic. O fluxo default roda **sem checkpointer** (sessões são one-shot; um saver compartilhado acumularia estado de todas as sessões); para **replay/recovery** há um `RedisCheckpointer` (TTL 1 h) injetável via `build_agent_graph(checkpointer)`.

### 🏪 Seller — gestão de catálogo

Vendedores rodam um loop procedural mais simples: auditam inventário, leem alertas de estoque baixo, **repõem estoque** (`PATCH /products/{id}/stock`), criam produtos novos (título/descrição gerados por Qwen) e ajustam preços. São os clientes de escrita assíncronos que tornam a idempotência do endpoint de estoque essencial em produção.

### 🧑‍💼 Tech Lead — melhoria contínua dirigida por IA

Um agente com persona de tech lead sênior que usa **DeepSeek V4 Pro** para gerar tarefas técnicas reais a partir de um *backlog blueprint*. Cada tarefa carrega **critérios de aceite executáveis** (existência de tabela no Postgres, endpoint registrado no OpenAPI, métrica no Prometheus, padrão de commit no git, suíte pytest verde) — o agente **avalia automaticamente** a entrega e fecha a tarefa quando todos os checks passam. Custo por tarefa rastreado em USD. Quadro Kanban em `/tasks.html`.

Documentação completa em **[docs/tech-lead-agent.md](docs/tech-lead-agent.md)**.

---

## Quickstart

> **Pré-requisitos:** Docker (Compose v2+), Ollama com `qwen3:8b` baixado (`ollama pull qwen3:8b`) e a env de sistema `OLLAMA_NUM_PARALLEL>=4` para o semáforo do app não serializar no Ollama, e os sistemas vizinhos (`MeliSim`, data lake) com as redes Docker externas `melisim_melisim` e `melisimlake-net` ativas.

```bash
cp .env.example .env          # ajuste credenciais (ver seção Configuração)
make up                       # postgres + redis + prometheus + api + orchestrator + live-floor + ui
make migrate                  # aplica o schema (Alembic)
make ports                    # imprime as URLs de cada serviço

# Popular personas (escolha a estratégia):
make seed-synthetic COUNT=60  # sintéticas — rápido, sem Qwen (ideal para dev/CI)
make seed-personas COUNT=200  # via Qwen real — ~20-30 min, exige Ollama

# Subir a simulação:
make start AGENTS=50          # 50 buyers paralelos
make seed-sellers COUNT=5     # popula vendedores sintéticos
make start-sellers SELLERS=5  # ativa o pool de vendedores
make open-floor               # abre o Live Floor no browser

# Gerar tarefas técnicas com o Tech Lead Agent:
make tech-lead-task           # gera 1 task via DeepSeek
```

### Interfaces

| UI | URL | Descrição |
|---|---|---|
| **Live Floor** | http://localhost:8503 | Observabilidade em tempo real (WebSocket) — agentes se movendo entre estações |
| **Topology (NOC)** | http://localhost:8503/topology.html | Mapa de calor de tráfego e fluxos entre estações |
| **Tasks (Kanban)** | http://localhost:8503/tasks.html | Quadro do Tech Lead Agent — backlog → in progress → review → done |
| **API (Swagger)** | http://localhost:8101/docs | Control plane: start/stop/scale, sessions, personas, tasks |
| **Streamlit** | http://localhost:8502 | Inspeção de sessões, replay, métricas, load test |
| **Prometheus** | http://localhost:9091 | Métricas brutas |

> **Nota operacional:** o WebSocket do Live Floor enxerga apenas o pool do processo **API**. Se o container `orchestrator` também subir um pool (default), há dois pools no mesmo Ollama. Para usar Live Floor + `POST /start`, defina `MELICROWD_ORCHESTRATOR_AUTOSTART=false` e recrie os containers.

---

## Configuração

Todas as variáveis usam o prefixo `MELICROWD_` e são validadas por `pydantic-settings` (`src/melicrowd/config.py`). Destaques:

| Variável | Default | Função |
|---|---|---|
| `MELICROWD_QWEN_MODEL` | `qwen3:8b` | Modelo local servido pelo Ollama (validado por benchmark vs 14b) |
| `MELICROWD_QWEN_MAX_CONCURRENT` | `12` | Teto de chamadas Qwen concorrentes (semaphore) |
| `MELICROWD_DEFAULT_AGENT_COUNT` | `50` | Buyers no pool |
| `MELICROWD_DEEPSEEK_API_KEY` | — | Chave da API DeepSeek (Tech Lead Agent) |
| `MELICROWD_DEEPSEEK_MODEL` | `deepseek-v4-pro` | Modelo do Tech Lead Agent |
| `MELICROWD_MELISIM_RATE_LIMIT_PER_MINUTE` | `100` | Token bucket interno → respeita o gateway alvo |
| `MELICROWD_ORCHESTRATOR_AUTOSTART` | `true` | `false` para usar Live Floor + `/start` na API |

Veja `.env.example` para a lista completa.

---

## Stack tecnológico

- **Python 3.11** + **uvloop** — event loop async de alta performance
- **LangGraph 0.2** — state machine de agentes com checkpointers plugáveis (Redis)
- **Qwen 3 8B** via **Ollama** (LLM local) · **DeepSeek V4 Pro** (LLM cloud, OpenAI-compatible)
- **FastAPI 0.115** · **Streamlit 1.41** · **Typer** — control plane, UI e CLI
- **httpx 0.28** (async) · **tenacity 9** (retry exponencial) · **aiokafka 0.12**
- **PostgreSQL 16** + **asyncpg** + **SQLAlchemy 2.x async** + **Alembic**
- **Redis 7.4** (AOF, checkpointer, estado live)
- **Prometheus** + **Grafana** (dashboards provisionados) · **OpenTelemetry** (opcional)
- **React** (zero-build, via CDN) servido por **nginx** — frontend Live Floor / Topology / Tasks

---

## Métricas-alvo (calibradas com o varejo BR)

Rodando 50 buyers por 1 h+:

| Métrica | Real (BR 2024-25) | Alvo MeliCrowd |
|---|---|---|
| Taxa de conversão | 2–5 % | ~3 % |
| Abandono de carrinho | 60–80 % | ~70 % |
| Duração média da sessão | 6–10 min | ~8 min |
| Ticket médio | R$ 380 | ~R$ 400 |
| Sessões/hora | — | ≥ 100 |

Acompanhe ao vivo no Live Floor (`:8503`), no Streamlit (`:8502`) e no Prometheus (`:9091`).

---

## Integração com sistemas vizinhos

MeliCrowd compartilha redes Docker com dois sistemas e não os modifica:

- **MeliSim** (e-commerce alvo) — consumido via REST no `api-gateway`: `auth`, `products`, `products/search`, `orders`, `payments` (com `Idempotency-Key`) e `products/{id}/stock` (restock dos sellers).
- **Data lake** — recebe telemetria enriquecida via Kafka nos tópicos `events.simulator.session_started`, `events.simulator.decision_made`, `events.simulator.session_ended`.

A degradação é graciosa: se o broker Kafka cai, o publisher entra em modo *degraded* (no-op silencioso) e o pool de agentes continua rodando.

---

## Testes e qualidade

```bash
make lint            # ruff (check + format)
make typecheck       # mypy strict
make test            # unit (rápido, sem containers)
make test-integration # testcontainers: Postgres / Redis / Kafka
make test-e2e        # 50 agentes end-to-end
make coverage-html   # relatório HTML de cobertura
```

Convenções de código, padrão de commits e fluxo de PR em **[CONTRIBUTING.md](CONTRIBUTING.md)**.

---

## Estrutura do repositório

```
melicrowd/
├── src/melicrowd/
│   ├── config.py            # pydantic-settings (fonte única de verdade)
│   ├── personas/            # geração e persistência de personas (buyer)
│   ├── agents/              # buyer: grafo LangGraph (nodes/, prompts/, edges)
│   ├── sellers/             # seller: loop procedural (actions/, prompts/)
│   ├── tech_lead/           # Tech Lead Agent (DeepSeek): generator, evaluator, backlog
│   ├── execution/           # Markov, cliente MeliSim, Kafka publisher, rate limiter
│   ├── llm/                 # clientes Qwen/Ollama, pool semaphore, trace
│   ├── orchestrator/        # AgentPool, SellerPool, schedulers, lifecycle
│   ├── api/                 # FastAPI: routers (control, inspect, personas, sellers, tasks, websocket)
│   ├── observability/       # métricas Prometheus + LiveAgentTracker
│   └── ui/                  # Streamlit
├── frontend/                # React zero-build: Live Floor, Topology, Tasks
├── infra/                   # postgres (migrations), redis, prometheus, grafana, nginx
├── tests/                   # unit · integration · e2e
└── docs/                    # ARCHITECTURE, RUNBOOK, tech-lead-agent, blog_post
```

---

## Documentação

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — camadas, decisões de design, trade-offs explícitos.
- **[docs/tech-lead-agent.md](docs/tech-lead-agent.md)** — o agente adversarial de melhoria contínua.
- **[RUNBOOK.md](RUNBOOK.md)** — operação, troubleshooting e tuning.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — convenções de código e fluxo de contribuição.
- **[RECON.md](RECON.md)** — reconhecimento de pré-implementação (registro histórico).
- **[docs/blog_post.md](docs/blog_post.md)** — artigo técnico sobre o design.

---

## Licença

MIT.
