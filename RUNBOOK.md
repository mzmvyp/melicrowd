# Runbook — MeliCrowd

> Procedimentos operacionais: setup, verificações de saúde, troubleshooting,
> recovery e tuning. Cobre os três tipos de agente (buyer, seller, tech lead),
> o frontend em tempo real e as integrações externas.

## Setup inicial

```bash
# 1. Pré-requisitos
docker compose version       # v2+
ollama list                  # confirma qwen3:8b baixado
docker network ls            # melisim_melisim e melisimlake-net devem existir

# 2. Subir vizinhos (se ainda não estiverem rodando)
cd ../MeliSim && make up
cd ../melisimlake && make up

# 3. Subir MeliCrowd
cd ../MeliCrowd
cp .env.example .env
make up
make migrate
make status
```

## Verificações de saúde

```bash
make ps              # status dos containers
make status          # health endpoints
make dns-check       # resolução DNS para melisim-api-gateway e kafka
make logs            # tail em tempo real
```

## Troubleshooting

### 1. Erro "rede melisim_melisim não encontrada"

A rede só existe quando o MeliSim está rodando. Suba ele primeiro:

```bash
cd ../MeliSim && make up
docker network inspect melisim_melisim   # confirma
```

### 2. `make up` trava em "waiting for healthchecks"

Provavelmente migrations não foram aplicadas, ou o postgres não subiu.
Cheque os logs:

```bash
make logs
docker logs melicrowd-postgres
```

Se necessário, rebuilde do zero:

```bash
make down-v && make up
```

### 3. Qwen lento ou indisponível

```bash
# Confirma que Ollama está rodando no host
curl http://localhost:11434/api/tags

# Lista modelos baixados
ollama list

# Se qwen3:8b não estiver, baixe (~5GB):
ollama pull qwen3:8b
```

Quando o Qwen está saturado, MeliCrowd cai em fallback procedural — sessões
não param, mas o decision trace marca `fallback_used=true`. Veja:

```sql
SELECT node, COUNT(*) FILTER (WHERE fallback_used) * 100.0 / COUNT(*) AS pct_fallback
FROM melicrowd.decisions
WHERE timestamp > now() - interval '1 hour'
GROUP BY node;
```

### 4. Conversion rate fora do realismo (>10%)

Ajuste:

- `src/melicrowd/agents/prompts/checkout_decision.txt` — torne mais conservador
- `src/melicrowd/execution/markov.py` — aumente peso para `back_to_list`/`exit`

Confira em http://localhost:8502 (página Metrics) ou via SQL:

```sql
SELECT
  outcome,
  COUNT(*) AS total,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct
FROM melicrowd.sessions
WHERE ended_at > now() - interval '1 hour'
GROUP BY outcome;
```

### 5. Pool não respawna agentes após crash

`AgentPool._on_agent_done` deveria respawnar quando `len(_tasks) < target_size`.
Se não está acontecendo, provavelmente `_shutdown_event` foi setado
prematuramente. Verifique:

```bash
make logs-orchestrator | grep -i shutdown
```

### 6. Redis cheio (out of memory)

Maxmemory está em 512MB com `volatile-lru`. Se ficar cheio:

```bash
docker exec melicrowd-redis redis-cli INFO memory | grep used_memory_human
docker exec melicrowd-redis redis-cli FLUSHDB   # destrutivo: apaga sessões em vôo
```

Tune `MELICROWD_REDIS_CHECKPOINT_TTL_SECONDS` para baixo (default 3600s = 1h).

### 7. Live Floor não atualiza (agentes parados ou ausentes)

O frontend (`:8503`) consome **só** o WebSocket `ws://localhost:8101/ws/agents`,
que reflete o pool do processo **API**. Causas comuns:

- **Dois pools rodando.** Se `MELICROWD_ORCHESTRATOR_AUTOSTART=true` (default), o
  container `orchestrator` sobe seu próprio pool — invisível ao WebSocket da API.
  Para Live Floor + `POST /start`, defina `MELICROWD_ORCHESTRATOR_AUTOSTART=false`
  e recrie os containers (`make restart`).
- **Nenhum pool ativo.** Confirme que houve `make start AGENTS=N` (ou autostart).

```bash
# O WebSocket está vivo?
curl -fsS http://localhost:8101/status | jq '.pool'
# Quantos agentes a API enxerga?
curl -fsS http://localhost:8101/agents | jq 'length'
```

### 8. Pool de sellers não age

Sellers precisam de personas seller e de ativação própria:

```bash
make seed-sellers COUNT=5      # popula personas seller sintéticas
make start-sellers SELLERS=5   # ativa o pool de vendedores
docker exec melicrowd-postgres psql -U melicrowd -d melicrowd \
  -c "SELECT count(*) FROM melicrowd.seller_personas;"
```

Se os sellers não repõem estoque, verifique se o MeliSim está acessível (o
`restock` faz `PATCH /products/{id}/stock` no gateway) e olhe os logs do
orchestrator filtrando por `sellers`.

### 9. Tech Lead Agent — DeepSeek falha / cai em fallback

Sintoma: `POST /tasks/generate` retorna uma task com `llm_model: "fallback"` ou
descrição genérica.

```bash
# A chave está configurada?
docker compose exec api printenv MELICROWD_DEEPSEEK_API_KEY | head -c 8
# Teste direto da API (modelos disponíveis):
curl -s https://api.deepseek.com/v1/models \
  -H "Authorization: Bearer $MELICROWD_DEEPSEEK_API_KEY" | jq '.data[].id'
```

Causas e correções:

- **JSON truncado** → o prompt produz descrição + critérios longos; a DeepSeek é
  um *reasoning model* e gasta tokens antes do JSON. O cliente usa `max_tokens`
  alto e `timeout` de 180 s justamente por isso. Se voltar a truncar, suba o
  `max_tokens` no `generator.py`.
- **`response_format` rejeitado** → a DeepSeek exige a palavra "json" no prompt
  quando se usa `json_object`; o prompt já contém. Não remova.
- **Chave/quota inválida** → o pipeline cai em fallback procedural (não quebra),
  mas a task perde a riqueza. Renove a chave em `.env` e recrie a API.

### 10. Tech Lead Agent — task gerada repetida / nunca fecha

- **Repetida:** o gerador filtra itens de backlog já cobertos por tasks vivas
  (`backlog/in_progress/review/done/blocked`). Só `rejected` libera regeração do
  mesmo item.
- **Critérios sempre vermelhos:** confirme que o item de backlog tem
  `target: "melicrowd"`. Itens marcados `melisim` pertencem ao sistema-alvo e
  **não** são verificáveis pelo evaluator (que só checa o próprio MeliCrowd);
  por isso o gerador os ignora. Ver `docs/tech-lead-agent.md`.

## Recovery

### Sessão travada no Redis

```bash
docker exec melicrowd-redis redis-cli KEYS "checkpoint:*" | head -10
docker exec melicrowd-redis redis-cli DEL checkpoint:<session_id>
```

### Migration falhou no meio

```bash
make migrate-history             # vê em qual revision parou
make migrate-down                # volta 1
# corrija o problema
make migrate
```

## Tuning

| Variável                                 | Default | Tune para...                               |
|------------------------------------------|---------|--------------------------------------------|
| `MELICROWD_DEFAULT_AGENT_COUNT`          | 50      | mais buyers ↑ se CPU folgada               |
| `MELICROWD_QWEN_MAX_CONCURRENT`          | 12      | maior se o Ollama tem GPU dedicada com folga; menor se p99 degrada |
| `MELICROWD_QWEN_TIMEOUT_SECONDS`         | 60      | menor se Ollama é rápido (acelera fallback)|
| `MELICROWD_MELISIM_RATE_LIMIT_PER_MINUTE`| 100     | maior se MeliSim tiver rate limit relaxado |
| `MELICROWD_REDIS_CHECKPOINT_TTL_SECONDS` | 3600    | menor se sessões longas estão entupindo Redis |
| `MELICROWD_ORCHESTRATOR_AUTOSTART`       | true    | `false` para usar Live Floor + `POST /start` (evita pool duplo) |
| `MELICROWD_DEEPSEEK_MODEL`               | deepseek-v4-pro | trocar o modelo do Tech Lead Agent |
| `MELICROWD_TECH_LEAD_AUTO_EVALUATE_INTERVAL_SECONDS` | 300 | frequência da reavaliação automática de tasks em review |
