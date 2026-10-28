"""Orquestrador Central (Eduardo).

Hub que coordena os quatro agentes do projecto via LangGraph StateGraph:

    1. analisador   (Guidyanne)  -- stub: guidyanne_analyzer_node
    2. gestor       (Carlos)     -- stub: carlos_issue_node
    3. programador  (Ruben)      -- stub: ruben_programmer_node
    4. revisor      (Eduardo)    -- implementado: pytest + retry/PR

Arquitetura:
- ``state.py``   -- TypedDict ``AgentState`` (contrato partilhado).
- ``agent.py``   -- classe + função do revisor (``eduardo_reviewer_node``).
- ``graph.py``   -- construção + compilação do ``StateGraph``.
- ``__main__.py`` -- CLI entry point (``python -m orquestrador``).
"""
from __future__ import annotations

from orquestrador.agent import Revisorteste, eduardo_reviewer_node
from orquestrador.graph import build_graph, orchestrator, should_retry_or_pr
from orquestrador.state import AgentState

__version__ = "0.1.0"

__all__ = [
    "AgentState",
    "Revisorteste",
    "build_graph",
    "orchestrator",
    "should_retry_or_pr",
    "eduardo_reviewer_node",
]
