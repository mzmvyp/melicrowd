# Runbook — MeliCrowd

> Procedimentos operacionais. Será expandido na Fase 10 com 10+ cenários.

## Setup inicial

```bash
# 1. Pré-requisitos
docker compose version       # v2+
ollama list                  # confirma qwen3:14b baixado
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

# Se qwen3:14b não estiver, baixe (~9GB, demora):
ollama pull qwen3:14b
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

| Variável                              | Default | Tune para...                               |
|---------------------------------------|---------|--------------------------------------------|
| `MELICROWD_DEFAULT_AGENT_COUNT`       | 50      | mais agentes ↑ se CPU folgada              |
| `MELICROWD_QWEN_MAX_CONCURRENT`       | 4       | maior se Ollama tem GPU dedicada           |
| `MELICROWD_QWEN_TIMEOUT_SECONDS`      | 60      | menor se Ollama é rápido (acelera fallback)|
| `MELICROWD_MELISIM_RATE_LIMIT_PER_MIN`| 100     | maior se MeliSim tiver rate limit relaxado |
| `MELICROWD_REDIS_CHECKPOINT_TTL_SECONDS` | 3600 | menor se sessões longas estão entupindo Redis |
