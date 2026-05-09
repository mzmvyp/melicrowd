# =============================================================================
# MeliCrowd — Makefile
# Targets simétricos: ciclo de vida, dev, testes, observabilidade.
# Use `make help` para a lista comentada.
# =============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose
PROJECT := melicrowd

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help: ## Mostra todos os targets com descrição
	@grep -E '^[a-zA-Z_%-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

.PHONY: up
up: check-deps ## Sobe a stack (postgres, redis, prometheus, api, orchestrator, ui)
	$(COMPOSE) up -d --build
	@echo ""
	@echo "MeliCrowd subindo. Aguardando healthchecks..."
	@$(MAKE) wait-healthy
	@$(MAKE) ps

.PHONY: down
down: ## Para a stack (preserva volumes)
	$(COMPOSE) down

.PHONY: down-v
down-v: ## Para a stack e remove volumes (DESTRUTIVO — apaga personas e sessões)
	@read -p "Apagar TODOS os volumes (personas, sessões, métricas)? [y/N] " ans; \
	  if [ "$$ans" = "y" ]; then $(COMPOSE) down -v; else echo "Cancelado."; fi

.PHONY: restart
restart: down up ## Reinicia a stack

.PHONY: ps
ps: ## Lista containers e status
	$(COMPOSE) ps

.PHONY: logs
logs: ## Logs em tempo real (todos os serviços)
	$(COMPOSE) logs -f --tail=100

.PHONY: logs-api
logs-api: ## Logs apenas do api
	$(COMPOSE) logs -f --tail=200 api

.PHONY: logs-orchestrator
logs-orchestrator: ## Logs apenas do orchestrator
	$(COMPOSE) logs -f --tail=200 orchestrator

.PHONY: logs-ui
logs-ui: ## Logs apenas do ui
	$(COMPOSE) logs -f --tail=200 ui

.PHONY: clean
clean: ## Remove containers parados e imagens dangling
	docker system prune -f

# ---------------------------------------------------------------------------
# Pré-requisitos / saúde
# ---------------------------------------------------------------------------

.PHONY: check-deps
check-deps: ## Valida que as redes externas (melisim_melisim, melisimlake-net) existem
	@docker network inspect melisim_melisim >/dev/null 2>&1 || \
	  (echo "❌ rede melisim_melisim não encontrada — suba MeliSim primeiro (cd ../MeliSim && make up)" && exit 1)
	@docker network inspect melisimlake-net >/dev/null 2>&1 || \
	  (echo "❌ rede melisimlake-net não encontrada — suba melisimlake primeiro (cd ../melisimlake && make up)" && exit 1)
	@echo "✓ redes externas presentes"

.PHONY: wait-healthy
wait-healthy: ## Espera todos os containers ficarem healthy (timeout 120s)
	@deadline=$$(($$(date +%s) + 120)); \
	  while true; do \
	    unhealthy=$$($(COMPOSE) ps --format json | grep -v '"Health":"healthy"' | grep -c '"State":"running"' || true); \
	    if [ "$$unhealthy" = "0" ]; then echo "✓ todos os serviços healthy"; break; fi; \
	    if [ $$(date +%s) -gt $$deadline ]; then echo "⚠ timeout esperando healthchecks"; $(COMPOSE) ps; exit 1; fi; \
	    sleep 2; \
	  done

.PHONY: status
status: ## Verifica health endpoints expostos
	@echo "=== api ==="
	@curl -fsS http://localhost:8101/health || echo "FAIL"
	@echo ""
	@echo "=== prometheus ==="
	@curl -fsS http://localhost:9091/-/healthy || echo "FAIL"
	@echo ""
	@echo "=== ui ==="
	@curl -fsS http://localhost:8502/_stcore/health || echo "FAIL"

.PHONY: dns-check
dns-check: ## Confirma que orchestrator resolve melisim-api-gateway e kafka
	@$(COMPOSE) exec orchestrator python -c "import socket; \
	  print('melisim-api-gateway →', socket.gethostbyname('melisim-api-gateway')); \
	  print('kafka →', socket.gethostbyname('kafka'))"

# ---------------------------------------------------------------------------
# Migrações Alembic
# ---------------------------------------------------------------------------

.PHONY: migrate
migrate: ## Aplica migrations Alembic (head)
	$(COMPOSE) run --rm api alembic upgrade head

.PHONY: migrate-down
migrate-down: ## Reverte 1 migration
	$(COMPOSE) run --rm api alembic downgrade -1

.PHONY: migrate-create
migrate-create: ## Gera migration nova: make migrate-create MSG="add foo"
	@if [ -z "$(MSG)" ]; then echo "Use: make migrate-create MSG='descrição'"; exit 1; fi
	$(COMPOSE) run --rm api alembic revision --autogenerate -m "$(MSG)"

.PHONY: migrate-history
migrate-history: ## Mostra histórico de migrations
	$(COMPOSE) run --rm api alembic history --verbose

# ---------------------------------------------------------------------------
# Operação dos agentes (placeholders — implementação real nas Fases 5-6)
# ---------------------------------------------------------------------------

.PHONY: start
start: ## Inicia o pool de agentes: make start AGENTS=50
	@count=$${AGENTS:-50}; \
	  curl -fsS -X POST "http://localhost:8101/start?agents=$$count" | jq

.PHONY: stop
stop: ## Para o pool gracefully
	@curl -fsS -X POST "http://localhost:8101/stop?graceful=true" | jq

.PHONY: scale
scale: ## Redimensiona o pool: make scale AGENTS=100
	@count=$${AGENTS:-50}; \
	  curl -fsS -X POST "http://localhost:8101/scale?agents=$$count" | jq

.PHONY: seed-personas
seed-personas: ## Gera N personas via Qwen: make seed-personas COUNT=200
	@n=$${COUNT:-200}; \
	  curl -fsS -X POST "http://localhost:8101/personas/generate?count=$$n" | jq

# ---------------------------------------------------------------------------
# Qualidade de código
# ---------------------------------------------------------------------------

.PHONY: lint
lint: ## Roda ruff (check + format check)
	poetry run ruff check src/ tests/
	poetry run ruff format --check src/ tests/

.PHONY: format
format: ## Auto-formata e aplica fixes
	poetry run ruff format src/ tests/
	poetry run ruff check --fix src/ tests/

.PHONY: typecheck
typecheck: ## Roda mypy strict
	poetry run mypy src/melicrowd

.PHONY: precommit-install
precommit-install: ## Instala hooks pre-commit
	poetry run pre-commit install

.PHONY: precommit-run
precommit-run: ## Executa todos os hooks em todos os arquivos
	poetry run pre-commit run --all-files

# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

.PHONY: test
test: ## Roda testes unitários (rápidos, sem containers)
	poetry run pytest tests/unit -v --cov=melicrowd --cov-report=term-missing

.PHONY: test-integration
test-integration: ## Roda testes de integração (testcontainers — Postgres/Redis/Kafka)
	poetry run pytest tests/integration -v -m integration --timeout=300

.PHONY: test-e2e
test-e2e: ## Roda testes E2E (50 agentes por 15min)
	poetry run pytest tests/e2e -v -m e2e --timeout=1800

.PHONY: test-all
test-all: test test-integration test-e2e ## Roda toda a suíte

.PHONY: coverage-html
coverage-html: ## Gera relatório HTML de cobertura
	poetry run pytest tests/unit --cov=melicrowd --cov-report=html
	@echo "Relatório em htmlcov/index.html"

# ---------------------------------------------------------------------------
# Atalhos para abrir UIs
# ---------------------------------------------------------------------------

.PHONY: open-ui
open-ui: ## Abre Streamlit no browser
	@python -m webbrowser http://localhost:8502 || echo "Abra http://localhost:8502"

.PHONY: open-api
open-api: ## Abre Swagger da API
	@python -m webbrowser http://localhost:8101/docs || echo "Abra http://localhost:8101/docs"

.PHONY: open-prometheus
open-prometheus: ## Abre Prometheus
	@python -m webbrowser http://localhost:9091 || echo "Abra http://localhost:9091"

.PHONY: ports
ports: ## Lista as portas expostas pelo MeliCrowd
	@echo ""
	@echo "  Serviço          URL                              Credencial"
	@echo "  ──────────────   ────────────────────────────     ─────────────────"
	@echo "  api (Swagger)    http://localhost:8101/docs       —"
	@echo "  ui (Streamlit)   http://localhost:8502            —"
	@echo "  prometheus       http://localhost:9091            —"
	@echo "  postgres         localhost:5437                   melicrowd/melicrowd123"
	@echo "  redis            localhost:6381                   —"
	@echo ""
