"""Agente Programador: aplica correções de código numa branch Git isolada.

Lê o ficheiro afetado por uma issue, substitui o código problemático e
confirma a alteração numa branch `fix/issue-{id}`, pronta para revisão.
O agente é injetável (fixer callable) e compatível com o estado partilhado
entre agentes no Hermes/LangGraph.
"""

from agente_programador.agent import ProgramadorAgent
from agente_programador.schemas import ProgramadorResult

__all__ = ["ProgramadorAgent", "ProgramadorResult"]
__version__ = "0.1.0"
