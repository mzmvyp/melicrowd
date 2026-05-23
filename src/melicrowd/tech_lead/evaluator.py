"""Evaluator — roda os AcceptanceChecks de uma task e devolve resultado.

5 kinds suportados:
- http:             chama URL com método/payload e compara status/body
- db:               executa SQL no Postgres do MeliCrowd
- metric:           consulta /metrics e checa valor mínimo
- git:              regex em log de commits OU arquivo existe no working tree
- test:             roda pytest path específico
- endpoint_exists:  consulta /openapi.json e verifica path+method

Importante: o evaluator é IDEMPOTENTE — pode rodar 100x sem efeito colateral.
"""
from __future__ import annotations

import re
import subprocess  # noqa: S404  — git/pytest precisam de subprocess
from collections.abc import Iterable
from typing import Any, Final

import httpx
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from melicrowd.config import settings
from melicrowd.tech_lead.models import AcceptanceCheck, CheckKind, CheckResult

LOGGER: Final = logger.bind(module="tech_lead.evaluator")

# Em produção API roda em http://api:8101 (rede docker); em dev host pode usar localhost:8101.
# Auto-detect: variável de ambiente do compose setada → estamos dentro do container.
import os as _os

_INTERNAL_API_BASE = "http://api:8101" if _os.environ.get("MELICROWD_RUNTIME") == "container" else "http://localhost:8101"


async def evaluate_task(checks: Iterable[AcceptanceCheck], db: AsyncSession) -> list[CheckResult]:
    """Roda todos os checks e devolve resultados na mesma ordem."""
    results: list[CheckResult] = []
    for check in checks:
        try:
            result = await _evaluate_one(check, db)
        except Exception as exc:  # noqa: BLE001 — falhar UM check não para os outros
            result = CheckResult(
                check=check,
                passed=False,
                detail=f"evaluator crashed: {type(exc).__name__}: {str(exc)[:200]}",
            )
        results.append(result)
    return results


async def _evaluate_one(check: AcceptanceCheck, db: AsyncSession) -> CheckResult:
    kind = CheckKind(check.kind) if isinstance(check.kind, str) else check.kind
    if kind == CheckKind.HTTP:
        return await _check_http(check)
    if kind == CheckKind.DB:
        return await _check_db(check, db)
    if kind == CheckKind.METRIC:
        return await _check_metric(check)
    if kind == CheckKind.GIT:
        return _check_git(check)
    if kind == CheckKind.TEST:
        return _check_test(check)
    if kind == CheckKind.ENDPOINT_EXISTS:
        return await _check_endpoint_exists(check)
    return CheckResult(check=check, passed=False, detail=f"kind {kind} não suportado")


async def _check_http(check: AcceptanceCheck) -> CheckResult:
    if not check.url:
        return CheckResult(check=check, passed=False, detail="url ausente")
    method = (check.method or "GET").upper()
    expected = check.expected_status or 200
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.request(
                method, check.url, json=check.request_body if method != "GET" else None
            )
        except Exception as exc:  # noqa: BLE001
            return CheckResult(check=check, passed=False, detail=f"http error: {type(exc).__name__}")
    if response.status_code != expected:
        return CheckResult(
            check=check,
            passed=False,
            detail=f"esperado {expected}, recebeu {response.status_code}: {response.text[:120]}",
        )
    if check.response_contains and check.response_contains not in response.text:
        return CheckResult(
            check=check,
            passed=False,
            detail=f"status ok mas body não contém '{check.response_contains}'",
        )
    return CheckResult(check=check, passed=True, detail=f"HTTP {response.status_code} ✓")


async def _check_db(check: AcceptanceCheck, db: AsyncSession) -> CheckResult:
    if not check.query:
        return CheckResult(check=check, passed=False, detail="query ausente")
    try:
        result = await db.execute(text(check.query))
        rows = result.fetchall()
    except Exception as exc:  # noqa: BLE001
        return CheckResult(check=check, passed=False, detail=f"SQL error: {type(exc).__name__}: {str(exc)[:160]}")
    if check.expect_min_rows is not None and len(rows) < check.expect_min_rows:
        return CheckResult(
            check=check,
            passed=False,
            detail=f"esperado ≥ {check.expect_min_rows} linhas, recebeu {len(rows)}",
        )
    if check.expect_value is not None:
        if not rows or str(rows[0][0]) != check.expect_value:
            actual = rows[0][0] if rows else None
            return CheckResult(check=check, passed=False, detail=f"esperado {check.expect_value!r}, recebeu {actual!r}")
    return CheckResult(check=check, passed=True, detail=f"DB ok ({len(rows)} linhas)")


async def _check_metric(check: AcceptanceCheck) -> CheckResult:
    if not check.metric_name:
        return CheckResult(check=check, passed=False, detail="metric_name ausente")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{_INTERNAL_API_BASE}/metrics")
        except Exception as exc:  # noqa: BLE001
            return CheckResult(check=check, passed=False, detail=f"metrics endpoint inacessível: {type(exc).__name__}")
    body = response.text
    # Procura linha tipo: metric_name{...} 42.0   ou   metric_name 42.0
    pattern = re.compile(rf"^{re.escape(check.metric_name)}(?:\{{[^}}]*\}})?\s+([0-9.eE+\-]+)", re.MULTILINE)
    matches = pattern.findall(body)
    if not matches:
        return CheckResult(check=check, passed=False, detail=f"métrica '{check.metric_name}' não encontrada")
    max_val = max(float(m) for m in matches)
    min_required = check.metric_min_value if check.metric_min_value is not None else 0.0
    if max_val < min_required:
        return CheckResult(
            check=check, passed=False, detail=f"métrica atual {max_val} < esperado {min_required}"
        )
    return CheckResult(check=check, passed=True, detail=f"métrica {check.metric_name}={max_val} ✓")


def _check_git(check: AcceptanceCheck) -> CheckResult:
    if check.git_file_exists:
        import os.path

        full_path = os.path.join(_PROJECT_ROOT, check.git_file_exists)
        if os.path.exists(full_path):
            return CheckResult(check=check, passed=True, detail=f"arquivo {check.git_file_exists} existe")
        return CheckResult(check=check, passed=False, detail=f"arquivo {check.git_file_exists} não existe")

    if not check.git_pattern:
        return CheckResult(check=check, passed=False, detail="git_pattern ausente")
    try:
        out = subprocess.run(  # noqa: S603 — pattern controlado pelo LLM trusted
            ["git", "log", "--oneline", "-n", "50"],
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
            timeout=10,
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(check=check, passed=False, detail=f"git error: {type(exc).__name__}")
    if re.search(check.git_pattern, out.stdout):
        return CheckResult(check=check, passed=True, detail="commit match ✓")
    return CheckResult(check=check, passed=False, detail=f"nenhum commit dos últimos 50 bate '{check.git_pattern}'")


def _check_test(check: AcceptanceCheck) -> CheckResult:
    if not check.pytest_path:
        return CheckResult(check=check, passed=False, detail="pytest_path ausente")
    try:
        out = subprocess.run(  # noqa: S603
            ["python", "-m", "pytest", check.pytest_path, "-q", "--no-header", "--tb=no"],
            capture_output=True,
            text=True,
            cwd=_PROJECT_ROOT,
            timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(check=check, passed=False, detail=f"pytest error: {type(exc).__name__}")
    if out.returncode == 0:
        return CheckResult(check=check, passed=True, detail="pytest passou ✓")
    return CheckResult(check=check, passed=False, detail=f"pytest falhou (exit {out.returncode})")


async def _check_endpoint_exists(check: AcceptanceCheck) -> CheckResult:
    if not check.openapi_path:
        return CheckResult(check=check, passed=False, detail="openapi_path ausente")
    method = (check.openapi_method or "GET").lower()
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(f"{_INTERNAL_API_BASE}/openapi.json")
            response.raise_for_status()
            spec = response.json()
        except Exception as exc:  # noqa: BLE001
            return CheckResult(check=check, passed=False, detail=f"openapi inacessível: {type(exc).__name__}")
    paths = spec.get("paths", {}) if isinstance(spec, dict) else {}
    # FastAPI normaliza {id} no path. Aceita match exato ou normalizado.
    expected_path = check.openapi_path
    if expected_path in paths and method in paths[expected_path]:
        return CheckResult(check=check, passed=True, detail="endpoint registrado ✓")
    # Tolera placeholders diferentes — compara estrutura.
    norm_expected = re.sub(r"\{[^}]+\}", "{x}", expected_path)
    for p in paths:
        if re.sub(r"\{[^}]+\}", "{x}", p) == norm_expected and method in paths[p]:
            return CheckResult(check=check, passed=True, detail=f"endpoint registrado em {p} ✓")
    return CheckResult(check=check, passed=False, detail=f"path {method.upper()} {expected_path} não está no OpenAPI")


# Root absoluto do projeto (usado por git/pytest checks).
_PROJECT_ROOT: Final[str] = "/app" if _os.environ.get("MELICROWD_RUNTIME") == "container" else _os.getcwd()
