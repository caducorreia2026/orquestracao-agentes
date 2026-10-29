"""Agente Revisor e Testador: orquestra runner + parser + formatter.

Desenhado para funcionar tanto como biblioteca standalone como como no de um
grafo LangGraph/Hermes. O contrato de estado e simples:

    Entrada (state):
        {
            "repo_path": str,            # obrigatorio
            "pytest_args": list[str],    # opcional
            "timeout": int,              # opcional (default 600s)
        }

    Saida (merge no estado):
        {
            "revisor_result": RevisorResult,
            "messages": [ <mensagem system com JSON do resultado> ],
        }
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from agente_revisor.formatter import build_result
from agente_revisor.pytest_runner import (
    PytestRun,
    PytestRunner,
    PytestNotFoundError,
    run_pytest,
)
from agente_revisor.schemas import RevisorResult

logger = logging.getLogger(__name__)


class RevisorAgent:
    """Agente Revisor: executa pytest e devolve erros estruturados.

    Exemplo:
        >>> agent = RevisorAgent()
        >>> state = {"repo_path": "/path/to/repo"}
        >>> out = agent.run(state)
        >>> print(out["revisor_result"].model_dump_json(indent=2))
    """

    def __init__(
        self,
        *,
        runner: Callable[..., PytestRun] = run_pytest,
    ) -> None:
        # `runner` e injetavel para facilitar testes (mock de subprocess).
        self._runner = runner

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Executa o ciclo completo: pytest -> parse -> format -> estado."""
        repo_path = state.get("repo_path")
        if not repo_path:
            raise ValueError("`state['repo_path']` e obrigatorio.")

        pytest_args: list[str] = list(state.get("pytest_args", []))
        timeout: int = int(state.get("timeout", 600))

        logger.info("Revisor: a executar pytest em %s", repo_path)
        try:
            pytest_run = self._runner(
                repo_path=repo_path,
                pytest_args=pytest_args,
                timeout=timeout,
            )
        except PytestNotFoundError as exc:
            logger.error("pytest nao encontrado: %s", exc)
            result = RevisorResult(
                repo_path=repo_path,
                status="error",
                exit_code=-1,
                error=str(exc),
            )
            return self._wrap(result)
        except TimeoutError as exc:
            logger.error("pytest timeout: %s", exc)
            result = RevisorResult(
                repo_path=repo_path,
                status="error",
                exit_code=-1,
                error=str(exc),
            )
            return self._wrap(result)

        result = build_result(repo_path=repo_path, pytest_run=pytest_run)
        logger.info(
            "Revisor: status=%s, failures=%d",
            result.status,
            len(result.failures),
        )
        return self._wrap(result)

    def as_node(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Devolve uma funcao compativel com um no LangGraph.

        Uso:
            graph.add_node("revisor", RevisorAgent().as_node())
        """

        def _node(state: dict[str, Any]) -> dict[str, Any]:
            return self.run(state)

        _node.__name__ = "revisor_node"
        return _node

    @staticmethod
    def _wrap(result: RevisorResult) -> dict[str, Any]:
        """Empacota o resultado no formato esperado pelo estado LangGraph."""
        return {
            "revisor_result": result,
            "messages": [result.to_langgraph_message()],
        }


__all__ = ["RevisorAgent"]
