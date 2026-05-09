#!/usr/bin/env bash
# =============================================================================
# MeliCrowd — Demo orchestration script
#
# Sobe os 3 sistemas (MeliSim, melisimlake, MeliCrowd) em ordem,
# gera 200 personas, inicia 50 agentes, deixa rodar 15min, encerra
# tudo gracefully.
# =============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SIBLINGS_BASE="$(dirname "$ROOT")"
MELISIM="$SIBLINGS_BASE/MeliSim"
MELISIMLAKE="$SIBLINGS_BASE/melisimlake"

say() { printf "\n\033[1;36m>>> %s\033[0m\n" "$*"; }
fail() { printf "\n\033[1;31m!!! %s\033[0m\n" "$*" >&2; exit 1; }

# Pré-flight
[ -d "$MELISIM" ] || fail "MeliSim não encontrado em $MELISIM"
[ -d "$MELISIMLAKE" ] || fail "melisimlake não encontrado em $MELISIMLAKE"
command -v docker >/dev/null || fail "docker não encontrado"
command -v ollama >/dev/null || say "aviso: ollama não encontrado no PATH — verifique manualmente"

say "1/6 subindo MeliSim"
( cd "$MELISIM" && make up )

say "2/6 subindo melisimlake"
( cd "$MELISIMLAKE" && make up && make init )

say "3/6 subindo MeliCrowd"
[ -f "$ROOT/.env" ] || cp "$ROOT/.env.example" "$ROOT/.env"
( cd "$ROOT" && make up && make migrate )

say "4/6 gerando 200 personas via Qwen (pode demorar 10-30min)"
( cd "$ROOT" && make seed-personas COUNT=200 )

say "5/6 iniciando 50 agentes — abrindo dashboards"
( cd "$ROOT" && make start AGENTS=50 )
say "Streamlit: http://localhost:8502"
say "API Swagger: http://localhost:8101/docs"
say "Prometheus: http://localhost:9091"

say "6/6 deixando rodar por 15min..."
sleep 900

say "encerrando MeliCrowd gracefully (drain 30s)"
( cd "$ROOT" && make stop )

say "DEMO concluída. Stack do MeliSim e melisimlake permanecem rodando."
say "Pra encerrar tudo: cd $MELISIM && make down ; cd $MELISIMLAKE && make down"
