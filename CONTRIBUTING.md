# Convenções de contribuição

Este documento descreve as convenções esperadas em qualquer mudança no
MeliCrowd: estilo de código, estrutura de módulos, fluxo de PR e padrão de
commits. Antes de abrir uma mudança, vale também ler **[ARCHITECTURE.md](ARCHITECTURE.md)**
para entender as camadas e os trade-offs do sistema.

## Onde sua mudança vive

| Tipo de mudança | Pacote |
|---|---|
| Comportamento de **buyer** (grafo, nós, prompts, edges) | `src/melicrowd/agents/` |
| Comportamento de **seller** (ações, prompts) | `src/melicrowd/sellers/` |
| **Tech Lead Agent** (backlog, gerador, evaluator, checks) | `src/melicrowd/tech_lead/` |
| Cliente LLM, pool e trace | `src/melicrowd/llm/` |
| Camada de execução (Markov, HTTP, Kafka, rate limit) | `src/melicrowd/execution/` |
| Lifecycle de pools e schedulers | `src/melicrowd/orchestrator/` |
| Routers/schemas FastAPI | `src/melicrowd/api/` |
| Migrations | `infra/postgres/migrations/versions/` |
| Frontend (Live Floor, Topology, Tasks) | `frontend/` |

## Estilo de código (não-negociável)

1. **Type hints em 100%** do código Python. Sem `Any` exceto interface com libs sem stubs.
2. **Docstrings estilo Google** em todas funções/métodos públicos.
3. **`from __future__ import annotations`** no topo de todo módulo.
4. **`Final`** para constantes de módulo.
5. **`loguru` apenas** — `print` é proibido (lint enforce).
6. **`pydantic-settings` apenas** — sem `os.environ` direto.
7. **Pydantic v2** para todo dado que cruza fronteira (HTTP, Kafka, DB).
8. **Português** para docstrings de domínio (persona, sessão, comportamento).
   **Inglês** para identificadores técnicos (function/var/class names).

## Estrutura de módulo (padrão)

```python
"""Módulo X — uma frase do que ele faz.

Parágrafo opcional de contexto.
"""
from __future__ import annotations

from typing import Final

from pydantic import BaseModel
from loguru import logger

from melicrowd.config import settings

LOGGER: Final = logger.bind(module="package.modulename")
DEFAULT_FOO: Final[int] = 42


class MyModel(BaseModel):
    """Descrição da classe.

    Atributos:
        field_a: explicação curta.
    """
    field_a: int


def public_fn(x: int) -> int:
    """Soma 1.

    Args:
        x: o número de entrada.

    Returns:
        ``x + 1``.
    """
    return x + 1
```

## Antes de commitar

```bash
make lint            # ruff
make typecheck       # mypy strict
make test            # pytest unit
```

Pre-commit hooks rodam automaticamente em `git commit` (instale com
`make precommit-install`).

## Commits

Conventional Commits, escopo por subsistema, descrição curta em inglês.

```
feat(buyers): add price-comparison node to LangGraph
feat(sellers): action update_price with category-aware percent
feat(tech-lead): add metric check kind to evaluator
fix(llm/pool): release semaphore on cancellation
test(orchestrator): cover graceful shutdown
docs(architecture): explain Tech Lead evaluator
chore(infra): pin postgres to 16.3
```

Escopos preferidos: `buyers`, `sellers`, `tech-lead`, `llm`, `execution`,
`orchestrator`, `api`, `frontend`, `infra`, `observability`.

Commits pequenos por sub-feature. Evite commits gigantes que misturem áreas.

## Quando fazer PR

- Código tem testes (≥ 75 % coverage no pacote tocado).
- `make lint typecheck test` passam localmente.
- `RUNBOOK.md` ou `ARCHITECTURE.md` atualizados quando o comportamento
  operacional ou as camadas mudam.
- Migrations Alembic com `downgrade` funcional.
- Sem segredos em arquivos versionados (`.env` está no `.gitignore`).
- Se a mudança envolve um endpoint novo ou uma métrica nova, ambos aparecem
  respectivamente em `/openapi.json` e em `/metrics` antes do merge.
