"""Agente Analisador: orquestra runner + parser + formatter.

Desenhado para funcionar tanto como biblioteca standalone como como nó de um
grafo LangGraph/Hermes. O contrato de estado é simples:

    Entrada (state):
        {
            "repo_path": str,            # obrigatório
            "pytest_args": list[str],    # opcional
            "timeout": int,              # opcional (default 600s)
        }

    Saída (merge no estado):
        {
            "analisador_result": AnalisadorResult,
            "messages": [ <mensagem system com JSON do resultado> ],
        }
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from agente_analisador.formatter import build_result
from agente_analisador.pytest_runner import PytestNotFoundError, run_pytest
from agente_analisador.schemas import AnalisadorResult

logger = logging.getLogger(__name__)


class AnalisadorAgent:
    """Agente que executa pytest e devolve erros estruturados.

    Exemplo:
        >>> agent = AnalisadorAgent()
        >>> state = {"repo_path": "/path/to/repo"}
        >>> out = agent.run(state)
        >>> print(out["analisador_result"].model_dump_json(indent=2))
    """

    def __init__(
        self,
        *,
        runner: Callable[..., Any] = run_pytest,
    ) -> None:
        # `runner` é injetável para facilitar testes (mock de subprocess).
        self._runner = runner

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Executa o ciclo completo: pytest -> parse -> format -> estado."""
        repo_path = state.get("repo_path")
        if not repo_path:
            raise ValueError("`state['repo_path']` é obrigatório.")

        pytest_args: list[str] = list(state.get("pytest_args", []))
        timeout: int = int(state.get("timeout", 600))

        logger.info("Analisador: a executar pytest em %s", repo_path)
        try:
            pytest_run = self._runner(
                repo_path=repo_path,
                pytest_args=pytest_args,
                timeout=timeout,
            )
        except PytestNotFoundError as exc:
            logger.error("pytest não encontrado: %s", exc)
            result = AnalisadorResult(
                repo_path=repo_path,
                status="error",
                error=str(exc),
            )
            return self._wrap(result)
        except TimeoutError as exc:
            logger.error("pytest timeout: %s", exc)
            result = AnalisadorResult(
                repo_path=repo_path,
                status="error",
                error=str(exc),
            )
            return self._wrap(result)

        result = build_result(repo_path=repo_path, pytest_run=pytest_run)
        logger.info(
            "Analisador: status=%s, failures=%d",
            result.status,
            len(result.failures),
        )
        return self._wrap(result)

    def as_node(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Devolve uma função compatível com um nó LangGraph.

        Uso:
            graph.add_node("analisador", AnalisadorAgent().as_node())
        """

        def _node(state: dict[str, Any]) -> dict[str, Any]:
            return self.run(state)

        _node.__name__ = "analisador_node"
        return _node

    @staticmethod
    def _wrap(result: AnalisadorResult) -> dict[str, Any]:
        """Empacota o resultado no formato esperado pelo estado LangGraph."""
        return {
            "analisador_result": result,
            "messages": [result.to_langgraph_message()],
        }
