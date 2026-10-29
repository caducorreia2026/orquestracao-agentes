"""Agente Revisor (Eduardo).

Executa o **pytest** num ambiente isolado via subprocess, capta stdout/stderr e
devolve um **relatorio estruturado** compativel com Hermes/LangGraph.

O pacote `agente_revisor` e o modulo interno onde reside a logica; este
`__init__.py` reexporta a API publica para importacao direta:

    from revisor import RevisorAgent, RevisorResult, build_result
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
