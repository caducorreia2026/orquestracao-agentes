"""Agente Revisor e Testador (Eduardo).

Executa o **pytest** num ambiente isolado via ``subprocess`` e devolve o
resultado ao orquestrador para decisão de retry/PR.

Contrato de estado (``AgentState``, ver ``state.py``):

    Entrada:
        state["repo_path"]  - caminho absoluto do repositório onde correr pytest.

    Saída (merge no estado):
        state["status"]       = "tests_passed"  | "tests_failed"
        state["test_results"]  = stdout + stderr capturado
        state["retry_count"]   = incrementado em +1 quando falha
"""
from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Callable
from typing import Any

from orquestrador.state import AgentState

logger = logging.getLogger(__name__)


class PytestRunner:
    """Runner injetável de pytest — isola ``subprocess`` para facilitar testes.

    Exemplo:
        >>> runner = PytestRunner()
        >>> out = runner.run("/caminho/ao/repo")
        >>> out.returncode
        0
    """

    def __init__(self, *, timeout: int = 300) -> None:
        self._timeout = timeout

    def run(self, repo_path: str, pytest_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
        """Lança ``pytest`` de forma isolada dentro de ``repo_path``.

        O processo filho corre com ``cwd=repo_path``, o que isola a pasta de
        trabalho.  ``stdout`` e ``stderr`` são capturados e devolvidos juntos.
        """
        cmd = [sys.executable, "-m", "pytest", "-v"]
        if pytest_args:
            cmd.extend(pytest_args)
        logger.info("Revisor: a correr pytest em %s", repo_path)
        return subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=self._timeout,
        )


class Revisorteste:
    """Agente Revisor e Testador.

    Orquestra a execução do pytest e o merge dos resultados no estado.

    Exemplo:
        >>> agent = Revisorteste()
        >>> state = AgentState(repo_path="/r", bug_description="b",
        ...                    issue_number=1, branch_name=None,
        ...                    test_results="", retry_count=0, status="ready")
        >>> out = agent.run(state)
        >>> out["status"] in ("tests_passed", "tests_failed")
        True
    """

    def __init__(
        self,
        *,
        runner: PytestRunner | Callable[..., Any] = PytestRunner(),
    ) -> None:
        self._runner = runner

    def run(self, state: AgentState) -> AgentState:
        """Executa pytest e atualiza o estado com ``status``/``retry_count``."""
        repo_path: str = state["repo_path"]

        try:
            result = self._runner.run(repo_path=repo_path)
        except subprocess.TimeoutExpired as exc:
            logger.error("pytest timeout: %s", exc)
            state["test_results"] = str(exc)
            state["status"] = "tests_failed"
            state["retry_count"] += 1
            return state
        except FileNotFoundError as exc:
            logger.error("pytest não encontrado: %s", exc)
            state["test_results"] = str(exc)
            state["status"] = "tests_failed"
            state["retry_count"] += 1
            return state

        combined = (result.stdout or "") + (result.stderr or "")
        state["test_results"] = combined

        if result.returncode == 0:
            state["status"] = "tests_passed"
        else:
            state["status"] = "tests_failed"
            state["retry_count"] += 1

        logger.info(
            "Revisor: status=%s retry_count=%d",
            state["status"], state["retry_count"],
        )
        return state

    def as_node(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Devolve uma função compatível com um nó LangGraph.

        Uso:
            graph.add_node("revisor", Revisorteste().as_node())
        """
        def _node(state: dict[str, Any]) -> dict[str, Any]:
            agent_state = state  # type: ignore[assignment]
            agent_state["revisor_result"] = self.run(agent_state)  # type: ignore[typeddict-item]
            return agent_state

        _node.__name__ = "eduardo_reviewer_node"
        return _node


# --- função-level (compatível com o grafo compilado no __init__.py) ---- #
# Mantida como função de topo-nível para integrar diretamente no StateGraph.
def eduardo_reviewer_node(state: dict[str, Any]) -> dict[str, Any]:
    """Nó do Agente Revisor e Testador (Eduardo).

    Executa ``pytest`` via ``subprocess`` num ambiente isolado (cwd=repo_path),
    captura stdout+stderr e actualiza:

      - ``status``       -> "tests_passed" ou "tests_failed"
      - ``test_results`` -> output combinado
      - ``retry_count``  -> incrementado em +1 quando falha
    """
    repo_path = state.get("repo_path", "")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=300,
    )
    combined = (result.stdout or "") + (result.stderr or "")
    state["test_results"] = combined

    if result.returncode == 0:
        state["status"] = "tests_passed"
    else:
        state["status"] = "tests_failed"
        state["retry_count"] = int(state.get("retry_count", 0)) + 1
    return state


__all__ = [
    "Revisorteste",
    "PytestRunner",
    "eduardo_reviewer_node",
]
