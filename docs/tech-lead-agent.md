# Tech Lead Agent

> Um agente operacional que dirige a **melhoria contínua** do próprio MeliCrowd:
> gera tarefas técnicas a partir de um backlog, define critérios de aceite
> **verificáveis por máquina**, avalia as entregas automaticamente e fecha o
> ticket quando todos os checks passam.

O Tech Lead Agent é o terceiro tipo de agente da plataforma. Diferente dos
buyers e sellers — que *exercitam* o sistema-alvo — ele atua sobre o **próprio
código do MeliCrowd**, formando um ciclo de evolução autônomo e auditável.

---

## Por que existe

Agentes de IA em produção raramente são "o LLM responde e pronto". O valor está
em **orquestrar** o LLM com (a) contexto persistente, (b) limites de
custo/latência e (c) **verificação objetiva** do resultado. O Tech Lead Agent é
a demonstração desse padrão: o LLM propõe trabalho, mas quem decide se o
trabalho está pronto é um conjunto de checks determinísticos — não o próprio
LLM. Isso elimina o risco de alucinação na hora de "dar a tarefa por concluída".

O paralelo direto com domínios regulados (fraude, compliance, risco): um agente
pode *sugerir* uma decisão, mas o fechamento depende de critérios objetivos e
de uma trilha de auditoria — exatamente o que este agente implementa.

---

## Ciclo de vida de uma tarefa

```
        ┌──────────┐  generate   ┌──────────────┐  start   ┌──────────────┐
        │ backlog  │ ──────────▶ │  backlog     │ ───────▶ │ in_progress  │
        │ blueprint│  (DeepSeek) │  (persistida)│          │ (SLA correndo)│
        └──────────┘             └──────────────┘          └──────┬───────┘
                                                                  │ submit
                                                                  ▼
   ┌────────┐   checks 100% verde   ┌────────┐   checks falham   ┌──────────┐
   │  done  │ ◀──────────────────── │ review │ ────────────────▶ │ blocked  │
   └────────┘     (evaluator)       └────────┘   (feedback)      └──────────┘
```

| Status | Significado |
|---|---|
| `backlog` | Tarefa gerada, ainda não iniciada |
| `in_progress` | Desenvolvedor começou; SLA correndo |
| `review` | Entrega submetida; evaluator rodou os checks |
| `done` | Todos os critérios de aceite passaram |
| `blocked` | Submetida mas reprovada nos checks (gera feedback) |
| `rejected` | Tarefa descartada (ex.: escopo inválido) |

---

## Componentes

```
src/melicrowd/tech_lead/
├── persona.py          # persona do tech lead (system prompt fixo)
├── backlog.json        # blueprint de ideias (não são tasks prontas)
├── deepseek_client.py  # cliente DeepSeek V4 Pro + cost tracking
├── prompts/            # generate_task.txt · evaluate_feedback.txt
├── generator.py        # pick backlog → DeepSeek → valida Pydantic → Task
├── evaluator.py        # roda os critérios de aceite (6 tipos de check)
├── models.py           # Task, AcceptanceCheck, CheckResult, enums
├── orm.py · repository.py
└── service.py          # orquestra generator + evaluator + persistência
```

### Persona

Uma persona de tech lead sênior fornece o *system prompt* fixo em toda chamada à
DeepSeek. Define tom, senioridade esperada do desenvolvedor e a stack do projeto
(FastAPI :8101, Postgres, Qwen via Ollama) — para que as tarefas geradas sejam
coerentes com o ambiente real.

### Backlog blueprint

`backlog.json` não contém tarefas prontas: contém **ideias** (headline,
rationale, categoria/prioridade sugeridas, hints e um campo `target`). O agente
escolhe um item ainda não coberto e pede à DeepSeek que o **expanda** numa
tarefa rica e específica.

> **`target` (`melicrowd` | `melisim`)** — marca a qual sistema a ideia
> pertence. O evaluator só consegue verificar critérios contra o próprio
> MeliCrowd (`http://api:8101`, schema `melicrowd`, repositório local), então o
> gerador filtra por `target=melicrowd`. Itens que pertencem ao sistema-alvo
> não são transformados em tarefas auto-avaliáveis — uma salvaguarda contra
> tarefas de escopo cruzado cujos critérios nunca fechariam.

### Geração (DeepSeek V4 Pro)

`generator.py` monta o prompt a partir do item de backlog, chama a DeepSeek com
`response_format: json_object`, valida a resposta com Pydantic
(`GeneratedTaskResponse`) e persiste a `Task`. Se a DeepSeek falhar (timeout,
JSON inválido, quota), há um **fallback** que produz uma tarefa mínima a partir
do próprio item de backlog — o pipeline nunca quebra.

O cliente rastreia o custo de cada chamada (input / output / cache) e o persiste
por tarefa (`generation_cost_usd`, `evaluation_cost_usd`). Custo típico de
geração: ~US$ 0,004 por tarefa.

### Avaliação objetiva

O `evaluator.py` suporta **6 tipos de check**, todos executáveis e idempotentes:

| Kind | O que verifica | Como |
|---|---|---|
| `db` | Estado do banco | Executa SQL no Postgres do MeliCrowd e checa linhas/valor |
| `endpoint_exists` | Contrato da API | Busca `path` + `method` no `/openapi.json` |
| `http` | Comportamento de runtime | Faz a requisição e compara status/corpo |
| `metric` | Observabilidade | Lê `/metrics` e checa a métrica Prometheus |
| `git` | Entrega versionada | `git log` casa um padrão, ou arquivo existe |
| `test` | Suíte automatizada | Roda um `pytest` específico e exige saída 0 |

Uma tarefa só vai para `done` quando **todos** os checks passam. Se algum falha
no estado `review`, a tarefa vai para `blocked` e o resultado de cada check fica
registrado (`last_check_results`) para orientar a correção.

---

## API

| Método | Rota | Função |
|---|---|---|
| `POST` | `/tasks/generate` | Gera 1 tarefa a partir do próximo item do backlog |
| `GET` | `/tasks` | Lista paginada + contagem por status |
| `GET` | `/tasks/{id}` | Detalhe de uma tarefa |
| `POST` | `/tasks/{id}/start` | `backlog → in_progress` (inicia o SLA) |
| `POST` | `/tasks/{id}/submit` | `→ review` e dispara a avaliação |
| `POST` | `/tasks/{id}/evaluate` | Re-roda os critérios sem mudar status |

## CLI

```bash
melicrowd tech-lead generate-task    # gera 1 task via DeepSeek
melicrowd tech-lead count            # contagem por status
melicrowd tech-lead evaluate <uuid>  # re-avalia uma task
```

## Interface (Kanban)

`/tasks.html` (servido em `:8503`) é um quadro Kanban com cinco colunas
(Backlog, In Progress, Review, Done, Blocked). Cada cartão mostra categoria,
prioridade, barra de SLA e os resultados de cada check (verde/vermelho). O
*drawer* exibe a descrição completa em markdown, os critérios de aceite com
status, o custo acumulado em USD e o histórico de feedback. Atualiza por
polling a cada 8 s.

---

## Decisões de design

- **Avaliação objetiva, não subjetiva.** O LLM nunca decide que a tarefa está
  pronta — quem decide são os checks. Elimina drift e dá auditoria.
- **DeepSeek para o tech lead, Qwen para buyers/sellers.** O Qwen local está
  ocupado com dezenas de agentes; a geração de tarefas exige *reasoning* longo,
  para o qual a DeepSeek V4 Pro tem ótimo custo-benefício (centavos por tarefa).
- **Backlog como blueprint, não como tarefas.** Separar "ideia" de "tarefa
  detalhada" deixa o LLM enriquecer com critérios mensuráveis sem perder o
  controle humano sobre o escopo.
- **Filtro por `target`.** Garante que toda tarefa auto-avaliável seja, de fato,
  verificável pelo evaluator — evita tickets que nunca fecham.
