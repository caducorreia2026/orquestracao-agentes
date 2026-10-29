"""Agente Revisor: executa pytest num repositorio local e devolve erros estruturados em JSON compativel com Hermes/LangGraph.

O pacote `agente_revisor` contem:
  - `RevisorAgent`       : classe principal do agente.
  - `RevisorResult`      : schema Pydantic do resultado estruturado.
  - `PytestRun`/`PytestRunner` : runner injetavel de subprocess.
  - `run_pytest`         : funcao standalone de execucao de pytest.
  - `build_result`       : formata saida bruta em RevisorResult.
  - `parse_failures`/`parse_summary` : parser da saida do pytest.
"""

from agente_revisor.agent import RevisorAgent
from agente_revisor.formatter import build_result
from agente_revisor.pytest_runner import (
    PytestNotFoundError,
    PytestRun,
    PytestRunner,
    run_pytest,
)
from agente_revisor.schemas import Failure, RevisorResult, Summary

__all__ = [
    "RevisorAgent",
    "RevisorResult",
    "Failure",
    "Summary",
    "PytestRun",
    "PytestRunner",
    "PytestNotFoundError",
    "run_pytest",
    "build_result",
]
__version__ = "0.1.0"
