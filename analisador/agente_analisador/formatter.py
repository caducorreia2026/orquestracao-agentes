"""Formata o resultado final do Agente Analisador em JSON estruturado.

Mantém a lógica de orquestração separada do parser/runner para que o agente
possa ser testado e estendido independentemente.
"""

from __future__ import annotations

import os

from agente_analisador.error_parser import parse_failures, parse_summary
from agente_analisador.pytest_runner import PytestRun
from agente_analisador.schemas import AnalisadorResult


def build_result(
    *,
    repo_path: str,
    pytest_run: PytestRun,
) -> AnalisadorResult:
    """Constrói um `AnalisadorResult` a partir da saída bruta do pytest.

    Regras de `status`:
      - "passed"  : pytest saiu com 0 e sem falhas.
      - "failed"  : pytest reportou falhas de teste.
      - "error"   : pytest reportou erros de coleção/execução.
      - "no_tests": pytest saiu com 5 (sem testes).
    """
    repo_path = os.path.abspath(repo_path)
    stdout = pytest_run.stdout
    stderr = pytest_run.stderr
    combined = stdout + ("\n" + stderr if stderr.strip() else "")

    summary = parse_summary(stdout)
    failures = parse_failures(stdout, repo_path)

    # Determina o status com base no returncode + conteúdo.
    if pytest_run.returncode == 0:
        status = "passed"
    elif pytest_run.returncode == 5:
        status = "no_tests"
    elif summary.errors > 0 and summary.failed == 0:
        status = "error"
    else:
        status = "failed"

    # Trunca raw_output para evitar payloads gigantes no estado do LangGraph.
    raw = combined
    if len(raw) > 20_000:
        raw = raw[:20_000] + "\n...[truncado]..."

    return AnalisadorResult(
        repo_path=repo_path,
        status=status,
        summary=summary,
        failures=failures,
        raw_output=raw,
        error=None if pytest_run.returncode in (0, 1, 5) else stderr.strip() or None,
    )
