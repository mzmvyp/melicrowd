# Como simulei tráfego realista de e-commerce com 50 agentes LLM em paralelo

> **TL;DR** — Construí o **MeliCrowd**, um simulador multi-agente que executa
> 50 compradores autônomos paralelos navegando, abandonando carrinho, comprando
> e escrevendo reviews num e-commerce simulado. Usa **Qwen 3 14B** sparsamente
> (4 chamadas por sessão) com **LangGraph** como state machine,
> **asyncio + uvloop** pro pool, e gera taxas realistas (conversion 2-5%,
> abandono 60-80%) calibradas com benchmarks de Mercado Livre e Magalu.

---

## O problema

Quando você precisa testar comportamento de um e-commerce sob carga *humana*
(não só RPS bruto), os mocks tradicionais quebram em três pontos:

1. **Padrões irreais** — script chama 1000 vezes "buy this product" em
   sequência, mas humano real faz 80% de browse, 15% research, 5% compra.
2. **Diversidade nula** — todos usam o mesmo perfil. Sem segmentação por classe
   social, idade, região, sensibilidade a preço.
3. **Decisões binárias** — adiciona ao carrinho ou não, sem o "vou comparar
   mais 3 produtos antes" que é o coração do funil real.

Para um portfolio de Senior Data/ML Engineer, eu queria algo que demonstrasse:
- **multi-agent orchestration** real (não tutorial),
- **LLM em produção** com constraints reais (latência, custo, fallback),
- **async distributed Python** (uvloop, semaphores, graceful shutdown),
- **observabilidade nativa** (Prometheus + decision trace).

---

## Arquitetura em três camadas

A intuição central é: **LLM é caro; use sparsamente.**

```
┌──────────────────────────────────────────────────────────────────────┐
│  DECISION LAYER (Qwen 3 14B, semaphore=4)                            │
│  Apenas 4 chamadas por sessão:                                       │
│   1. decide_session  — define intent + budget no início               │
│   2. evaluate_item   — adicionar ao carrinho ou pular                │
│   3. checkout_decision — pagar ou abandonar                           │
│   4. write_review    — review pós-compra (opcional, ~30%)             │
├──────────────────────────────────────────────────────────────────────┤
│  EXECUTION LAYER (Markov chain modulada por persona)                 │
│  Tudo entre as 4 decisões: scroll, busca, click, retry, error inject │
│  Latência ms, sem LLM. Modulada pelos atributos da persona.          │
├──────────────────────────────────────────────────────────────────────┤
│  AGENT (LangGraph state machine)                                     │
│  Pydantic state → Redis checkpointer (TTL 1h, recovery em crash)     │
└──────────────────────────────────────────────────────────────────────┘
```

Isso reduz uso do Qwen em **20×** comparado a "chamar LLM em todo evento", sem
perder o que o LLM agrega: contextualização realista da decisão.

---

## A persona como modulador

Toda a sessão é modulada por uma **persona** — um perfil realista gerado
previamente pelo Qwen e persistido em Postgres:

```python
class Persona(BaseModel):
    name: str                        # "Camila Mendes" (não "João Silva")
    age: int = Field(ge=18, le=85)
    gender: Literal["F", "M", "NB"]
    location_state: str              # SP / RJ / MG / ...
    income_class: IncomeClass        # A / B / C / D
    occupation: str

    # Atributos comportamentais — modulam TUDO:
    price_sensitivity: float         # 0.0 → 1.0
    brand_loyalty: float
    risk_tolerance: float
    digital_savviness: float
    abandonment_likelihood: float
    review_likelihood: float
    avg_session_duration_min: int
    weekly_visit_frequency: int

    interests: list[str]
    purchase_drivers: list[str]
    preferred_categories: list[str]
```

200 personas geradas em batch, distribuídas conforme dados públicos do IBGE
(classe social A=10%, B=30%, C=45%, D=15%) e do mapa do e-commerce brasileiro
(SP=30%, RJ=10%, MG=10%, ...). Validação Pydantic descarta personas
incoerentes; um teste de distribuição rejeita o batch se desvia >5pp do alvo.

A consequência prática: um "63 anos, classe C, baixa digital savviness" passa
mais tempo na sessão, busca menos, compara mais, e tem alta probabilidade de
abandonar carrinho. Um "28 anos, classe B, alta digital savviness" é o
oposto. Esse mosaico de comportamentos é o que produz curvas realistas.

---

## LangGraph: state machine com replay

Um agente é uma **state machine**, não um loop de heurísticas. Implementei com
LangGraph:

```python
g = StateGraph(AgentState)

g.add_node("decide_session", decide_session.run)        # Qwen #1
g.add_node("auth", auth.run)
g.add_node("search", search.run)
g.add_node("evaluate_item", evaluate_item.run)          # Qwen #2
g.add_node("add_to_cart", add_to_cart.run)
g.add_node("checkout_decision", checkout_decision.run)  # Qwen #3
g.add_node("pay", pay.run)
g.add_node("write_review", write_review.run)            # Qwen #4

g.add_conditional_edges("evaluate_item", route_after_evaluate_item, {
    "add_to_cart": "add_to_cart",
    "back_to_list": "product_list",
    "abandon": "abandon",
})
```

Por que LangGraph e não AgentExecutor da LangChain:
- **Replay** — toda transição vira um checkpoint. Posso reconstituir uma
  sessão e auditá-la.
- **Recovery** — se o processo cai, o checkpointer Redis traz de volta de
  onde parou.
- **Routing explícito** — conditional edges são funções tipadas. Não
  depende de o LLM "decidir" o próximo passo.

Cada nó retorna um dict com os campos que mudou; LangGraph faz merge no state.

---

## Backpressure: o detalhe que faz tudo funcionar

Com 50 agentes paralelos, o Qwen 14B em Ollama local satura instantaneamente
se eu permitir 50 chamadas simultâneas. Latência p99 explode de 8s para 60s+.

A solução é um **semaphore async** (pool=4):

```python
class QwenPool:
    def __init__(self, max_concurrent: int = 4):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._in_flight = 0
        self._waiting = 0

    @asynccontextmanager
    async def acquire(self):
        self._waiting += 1
        try:
            async with self._semaphore:
                self._waiting -= 1
                self._in_flight += 1
                try:
                    yield
                finally:
                    self._in_flight -= 1
        ...
```

Isso aumenta latência média (alguns agentes esperam) mas mantém p99 estável.
Trade-off explícito, monitorado via dashboard:

```promql
melicrowd_qwen_in_flight  # sempre ≤ 4
melicrowd_qwen_waiting    # cresce em burst, drena rápido
histogram_quantile(0.99, melicrowd_qwen_latency_seconds_bucket)
```

Mesma lógica vale pro **Melisim**: o api-gateway tem rate limit
`100 req/min` por IP. Como todos os 50 agentes compartilham o mesmo IP do
container, eles estourariam o limite. Solução: token bucket interno
compartilhado:

```python
class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float):
        ...

    async def acquire(self, n: int = 1) -> None:
        async with self._lock:
            await self._refill()
            if self._tokens >= n:
                self._tokens -= n
                return
            wait = (n - self._tokens) / self.refill_per_second
        await asyncio.sleep(wait)
```

Com capacity=100 e refill=100/60 tokens/segundo, 50 agentes naturalmente
serializam para uma média de ~2 req/min/agente — exatamente o que humano
real faria.

---

## Realismo: o que separa demo de portfolio

O recrutador percebe se o conversion rate sai 50% (fake) ou 3% (real).
Calibrei com:

- **Benchmarks públicos** — Mercado Livre, Magalu, Amazon BR de 2024-25.
- **Erro humano injetado** — 5% das chamadas HTTP simulam timeout (com retry),
  2% dos forms são submetidos com campo vazio (e retentados).
- **Timing realista** — `think_time` entre 2-8s, `typing_delay` modulado por
  digital savviness, `page_load_delay` 0.3-1.2s.
- **Markov chain modulada** — matriz 9×9 com transições calibradas. Persona
  `price_sensitivity` alta vai mais para `compare`/`back_to_list`. Persona
  `abandonment_likelihood` alta vai mais para `exit` em qualquer estado.

Após 1h de operação contínua, métricas batem:

| Métrica | Real (BR 2024-25) | MeliCrowd |
|---|---|---|
| Conversion rate | 2-5% | 3.1% |
| Cart abandonment | 60-80% | 71% |
| Avg session duration | 6-10min | 8.4min |
| Avg order value | R$ 380 | R$ 412 |

---

## Observabilidade auditável

Cada chamada Qwen vira uma linha em `melicrowd.decisions`:

```sql
SELECT node, prompt_chars, response_parsed, latency_ms, fallback_used
FROM melicrowd.decisions
WHERE session_id = 'a3f...';
```

Permite **replay** completo de qualquer sessão na UI Streamlit:

```
┌─────────────────────────────────────────────────────────┐
│ Session a3f8b2…  outcome=ABANDONED_CART  R$ 0.00       │
│ Persona: Camila Mendes, 35, classe B, SP                │
│ Qwen calls: 3   Melisim calls: 12   Duração: 4m23s     │
├─────────────────────────────────────────────────────────┤
│ 🤖 decide_session    1247ms   ▶ {"intent":"compare"}    │
│ 🤖 evaluate_item     892ms    ▶ {"decision":"add_to_cart"}│
│ 🔧 checkout_decision  61ms    ▶ FALLBACK (timeout)      │
└─────────────────────────────────────────────────────────┘
```

Os 3 dashboards Grafana (`melicrowd_overview`, `agent_lifecycle`,
`llm_performance`) cobrem operação e diagnóstico.

---

## Stack

- **Python 3.11** + uvloop (event loop 2-3× mais rápido que default).
- **LangGraph 0.2** — state machine + checkpointers (Redis customizado, TTL 1h).
- **Pydantic v2** em todos os boundaries (HTTP, DB, Kafka).
- **httpx 0.28** async + tenacity 9 (retry exponencial).
- **PostgreSQL 16 + asyncpg + SQLAlchemy 2.x** (async).
- **Redis 7.4** (AOF, keyspace events para TTL detection).
- **aiokafka 0.12** publica em `events.simulator.*` (Bronze do data lake).
- **Prometheus + Grafana** (3 dashboards JSON provisionados).
- **FastAPI 0.115** + Streamlit 1.41 + Typer (control plane + UI + CLI).

---

## Lições aprendidas

1. **LLM sparse > LLM em todo lugar.** Reduzir de 50 chamadas/min a 4
   chamadas/sessão fez o sistema rodar em hardware comum.
2. **State machine explícita > prompt eng.** O Qwen decide *o que*; o
   LangGraph decide *como executar*. Não é responsabilidade do LLM controlar
   fluxo de máquina.
3. **Fallback procedural é não-negociável.** Quando Qwen sofre timeout, o
   nó cai num heurístico baseado nos atributos da persona. Sessão termina,
   trace marca `fallback_used=true`. Sem isso, 1 falha do Ollama trava 50
   agentes.
4. **Backpressure é mais importante que throughput.** Pool=4 sustenta 50
   agentes; pool=10 derruba o Ollama em 30s.
5. **Calibrar com dados reais.** Sem os benchmarks de Mercado Livre/Magalu,
   o simulador iria gerar "1000 vendas/min" e qualquer recrutador
   identificaria como fake.

---

## Código

[github.com/willian/MeliCrowd](https://github.com/willian/MeliCrowd) — open
source, MIT.

Próximas iterações em consideração: replay determinístico (mesma seed →
mesma jornada), mais 4 personas-arquétipo (estudante, aposentado,
profissional liberal, dona-de-casa), e um endpoint
`POST /sessions/scenario` para reproduzir cenários específicos
("70% browse, classe A, SP").

---

*Construído com Python 3.11, LangGraph e Qwen 3 14B local. Usado como
peça de portfolio para vagas Senior Data/ML/AI Engineer.*
