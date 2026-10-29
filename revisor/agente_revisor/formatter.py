"""Formata o resultado final do Agente Revisor em JSON estruturado.

Mantem a logica de orquestracao separada do parser/runner para que o agente
possa ser testado e estendido independentemente.
"""

from __future__ import annotations

import os

from agente_revisor.error_parser import parse_failures, parse_summary
from agente_revisor.pytest_runner import PytestRun
from agente_revisor.schemas import RevisorResult


def build_result(
    *,
    repo_path: str,
    pytest_run: PytestRun,
) -> RevisorResult:
    """Constroi um RevisorResult a partir da saida bruta do pytest.

    Regras de status:
      - "passed"  : pytest saidu com 0 e sem falhas.
      - "failed"  : pytest reportou falhas de teste.
      - "error"   : pytest reportou erros de colecao/execucao.
      - "no_tests": pytest saidu com 5 (sem testes).
    """
    repo_path = os.path.abspath(repo_path)
    stdout = pytest_run.stdout
    stderr = pytest_run.stderr
    combined = stdout + ("\n" + stderr if stderr.strip() else "")

    summary = parse_summary(stdout)
    failures = parse_failures(stdout, repo_path)

    # Determina o status com base no returncode + conteudo.
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

    return RevisorResult(
        repo_path=repo_path,
        status=status,
        exit_code=pytest_run.returncode,
        summary=summary,
        failures=failures,
        raw_output=raw,
        error=None if pytest_run.returncode in (0, 1, 5) else stderr.strip() or None,
    )


__all__ = ["build_result"]
