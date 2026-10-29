"""Agente Revisor e Testador (Eduardo).

Executa o **pytest** num ambiente isolado via ``subprocess`` e devolve o
resultado ao orquestrador para decisao de retry/PR.

A logica do agente reside no pacote ``revisor/agente_revisor/`` (modulo
reutilizavel e testavel independentemente do orquestrador). Este modulo
fornece o wrapper ``Revisorteste`` e a funcao ``eduardo_reviewer_node`` que
adaptam o resultado do agente ao ``AgentState`` do orquestrador.

Contrato de estado (``AgentState``, ver ``state.py``):

    Entrada:
        state["repo_path"]  - caminho absoluto do repositorio onde correr pytest.

    Saida (merge no estado):
        state["status"]         = "tests_passed"  | "tests_failed"
        state["test_results"]   = stdout + stderr capturado
        state["retry_count"]    = incrementado em +1 quando falha
        state["revisor_result"] = RevisorResult (JSON estruturado, opcional)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from orquestrador.state import AgentState

logger = logging.getLogger(__name__)


class Revisorteste:
    """Agente Revisor e Testador.

    Delega a execucao do pytest ao ``RevisorAgent`` do pacote
    ``agente_revisor`` e adapta o resultado ao contrato do ``AgentState``
    do orquestrador.

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
        runner: Callable[..., Any] | None = None,
    ) -> None:
        # Importa aqui para evitar dependencia circular no nivel de modulo.
        from agente_revisor.agent import RevisorAgent

        self._agent: RevisorAgent = RevisorAgent(runner=runner) if runner else RevisorAgent()

    def run(self, state: AgentState) -> AgentState:
        """Executa pytest e atualiza o estado com ``status``/``retry_count``."""
        repo_path: str = state["repo_path"]

        # Constroi o estado de entrada para o RevisorAgent.
        revisor_state: dict[str, Any] = {"repo_path": repo_path}

        try:
            out = self._agent.run(revisor_state)
        except Exception as exc:  # noqa: BLE001
            logger.error("Revisor: falha inesperada: %s", exc)
            state["test_results"] = str(exc)
            state["status"] = "tests_failed"
            state["retry_count"] += 1
            return state

        # Armazena o resultado estruturado para consumo downstream.
        revisor_result = out["revisor_result"]
        state["revisor_result"] = revisor_result

        # Captura a saída bruta (stdout + stderr) no estado partilhado.
        state["test_results"] = revisor_result.raw_output

        if revisor_result.status == "passed":
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
        """Devolve uma funcao compativel com um no LangGraph.

        Uso:
            graph.add_node("revisor", Revisorteste().as_node())
        """

        def _node(state: dict[str, Any]) -> dict[str, Any]:
            agent_state = state  # type: ignore[assignment]
            result = self.run(agent_state)
            agent_state["revisor_result"] = result["revisor_result"]  # type: ignore[typeddict-item]
            return agent_state

        _node.__name__ = "eduardo_reviewer_node"
        return _node


# --- funcao-nivel (compativel com o grafo compilado no __init__.py) ---- #
# Mantida como funcao de topo-nivel para integrar diretamente no StateGraph.
def eduardo_reviewer_node(state: dict[str, Any]) -> dict[str, Any]:
    """No do Agente Revisor e Testador (Eduardo).

    Executa ``pytest`` via ``subprocess`` num ambiente isolado (cwd=repo_path),
    capta stdout+stderr e actualiza:

      - ``status``       -> "tests_passed" ou "tests_failed"
      - ``test_results``  -> output combinado
      - ``retry_count``   -> incrementado em +1 quando falha
    """
    from agente_revisor.agent import RevisorAgent

    repo_path = state.get("repo_path", "")
    agent = RevisorAgent()
    out = agent.run({"repo_path": repo_path})
    revisor_result = out["revisor_result"]

    state["revisor_result"] = revisor_result
    state["test_results"] = revisor_result.raw_output

    if revisor_result.status == "passed":
        state["status"] = "tests_passed"
    else:
        state["status"] = "tests_failed"
        state["retry_count"] = int(state.get("retry_count", 0)) + 1
    return state


__all__ = [
    "Revisorteste",
    "eduardo_reviewer_node",
]
