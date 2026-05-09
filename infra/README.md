# `infra/` — configuração de infraestrutura

Cada subpasta corresponde a um componente da stack do MeliCrowd.
Mudanças aqui geralmente exigem `make restart` para refletir nos containers.

| Pasta            | Conteúdo                                                  |
|------------------|-----------------------------------------------------------|
| `postgres/`      | `init.sql` (schema, extensions) + `migrations/` (Alembic) |
| `redis/`         | `redis.conf` (AOF, TTL keyspace events)                   |
| `prometheus/`    | `prometheus.yml` (scrape configs)                         |
| `grafana/`       | dashboards JSON (populados na Fase 7)                     |
| `logging/`       | configurações de logging (ex: uvicorn.json)               |

Convenção: nada aqui contém segredos. Tudo o que é segredo vai em `.env`.
