# Convenções de contribuição

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

Padrão: tema + escopo + descrição em inglês.

```
feat(personas): add Qwen-based generator
test(orchestrator): cover graceful shutdown
fix(llm/pool): release semaphore on cancellation
docs(architecture): explain backpressure decisions
chore(infra): pin postgres to 16.3
```

Commits pequenos por sub-feature. Evite commits gigantes.

## Quando fazer PR

- Código tem testes (≥75% coverage).
- `make lint typecheck test` passam localmente.
- `RUNBOOK.md` ou `ARCHITECTURE.md` atualizados se mudou comportamento operacional.
- Sem segredos em arquivos versionados.
