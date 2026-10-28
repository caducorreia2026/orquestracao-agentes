"""Grafo do Orquestrador Central (Eduardo).

Constrói o ``StateGraph`` do LangGraph que coordena os quatro agentes do
projecto:

    1. analisador    (Guidyanne)  -> node stub: guidyanne_analyzer_node
    2. gestor        (Carlos)     -> node stub: carlos_issue_node
    3. programador   (Ruben)      -> node stub: ruben_programmer_node
    4. revisor       (Eduardo)    -> eduardo_reviewer_node (implementado)

Fluxo:

    START -> analyzer -> issue_manager -> programmer -> reviewer
                                                           |
                                          should_retry_or_pr
                                                           |
                        +-----------+-----------+--------+
                        |           |                      |
                     create_pr   programmer (retry)      END (stop)

O ciclo programador -> revisor repete até aos 3 tentativas (``retry_count`` < 3).
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langgraph.graph import START, END, StateGraph

from orquestrador.agent import eduardo_reviewer_node
from orquestrador.state import AgentState


# ------------------------------------------------------------------ #
# Nós-stub dos colegas — substituir pelas implementações reais.       #
# ------------------------------------------------------------------ #
def guidyanne_analyzer_node(state: dict[str, Any]) -> dict[str, Any]:
    """Agente 1 (Guidyanne) — Analisador de Código.

    TODO (Guidyanne): analisar ``state["repo_path"]`` à procura de código
    falhado, reproduzir o bug, gerar um ``BugReport`` e colocar a descrição
    em ``state["bug_description"]``.

    Entradas:  state["repo_path"]
    Saídas:    state["bug_description"], state["status"]
    """
    return {**state, "bug_description": state.get("bug_description", ""), "status": "analyzed"}


def carlos_issue_node(state: dict[str, Any]) -> dict[str, Any]:
    """Agente 2 (Carlos) — Gestor de Issues.

    TODO (Carlos): a partir de ``bug_description`` criar ou deduplicar uma
    issue no GitHub, abrir a branch indicada e escrever o número real da
    issue em ``state["issue_number"]``.

    Entradas:  state["bug_description"], state["repo_path"]
    Saídas:    state["issue_number"], state["branch_name"], state["status"]
    """
    return {
        **state,
        "issue_number": state.get("issue_number", 0),
        "status": "issue_created",
    }


def ruben_programmer_node(state: dict[str, Any]) -> dict[str, Any]:
    """Agente 3 (Ruben) — Programador.

    TODO (Ruben): fazer checkout de ``branch_name`` e implementar a
    correção descrita em ``bug_description``.  Garantir que os testes
    relevantes passam antes de devolver o controlo ao revisor.

    Entradas:  state["repo_path"], state["branch_name"], state["bug_description"]
    Saídas:    state["status"]
    """
    return {**state, "status": "programmed"}


def pr_creation_node(state: dict[str, Any]) -> dict[str, Any]:
    """Passo final — cria o Pull Request no GitHub.

    TODO: integrar com a API do GitHub (``gh`` CLI ou ``requests``).
    Abre um PR a partir de ``branch_name`` para ``main``, linka a issue
    ``#issue_number`` e regista o resultado em ``state["status"]``.
    """
    return {**state, "status": "pr_created"}


# ------------------------------------------------------------------ #
# Roteamento condicional após o revisor.                              #
# ------------------------------------------------------------------ #
def should_retry_or_pr(state: dict[str, Any]) -> str:
    """Decide o próximo passo com base no resultado dos testes.

    - ``status == "tests_passed"``       -> "create_pr"
    - ``status == "tests_failed"`` e
      ``retry_count < 3``               -> "retry_programming" (volta ao Ruben)
    - ``retry_count >= 3``              -> "stop" (encerra limpo no END)
    """
    if state.get("status") == "tests_passed":
        return "create_pr"
    if int(state.get("retry_count", 0)) >= 3:
        return "stop"
    return "retry_programming"


# ------------------------------------------------------------------ #
# Construtor do StateGraph.                                           #
# ------------------------------------------------------------------ #
def build_graph() -> StateGraph:
    """Constrói e devolve o ``StateGraph`` orquestrador (não compilado)."""
    graph = StateGraph(AgentState)

    graph.add_node("analyzer", guidyanne_analyzer_node)
    graph.add_node("issue_manager", carlos_issue_node)
    graph.add_node("programmer", ruben_programmer_node)
    graph.add_node("reviewer", eduardo_reviewer_node)
    graph.add_node("create_pr", pr_creation_node)

    graph.add_edge(START, "analyzer")
    graph.add_edge("analyzer", "issue_manager")
    graph.add_edge("issue_manager", "programmer")
    graph.add_edge("programmer", "reviewer")

    graph.add_conditional_edges(
        "reviewer",
        should_retry_or_pr,
        {
            "create_pr": "create_pr",
            "retry_programming": "programmer",
            "stop": END,
        },
    )

    graph.add_edge("create_pr", END)
    return graph


# Grafo compilado (pronto para .invoke/.stream).
# O ``recursion_limit=50`` é passado a cada chamada via config:
#     orchestrator.invoke(state, config={"recursion_limit": 50})
orchestrator: Any = build_graph().compile()


__all__ = [
    "AgentState",
    "build_graph",
    "orchestrator",
    "should_retry_or_pr",
    "eduardo_reviewer_node",
    "guidyanne_analyzer_node",
    "carlos_issue_node",
    "ruben_programmer_node",
    "pr_creation_node",
]
