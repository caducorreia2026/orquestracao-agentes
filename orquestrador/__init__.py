"""Orquestrador Central (Eduardo).

Define o StateGraph do LangGraph que coordena os quatro agentes:

    1. analisador   (Guidyanne) - analisa o repo e devolve um BugReport
    2. gestor       (Carlos)    - cria/deduplica a issue no GitHub + branch
    3. programador  (Ruben)     - implementa a correção na branch
    4. revisor      (Eduardo)   - corre os testes; rejeita ao programador
                                  enquanto falham (até 3 tentativas), senão cria PR.

Ciclo: analyzer -> issue_manager -> programmer -> reviewer -> (create_pr | retry programmer | stop)
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any

from langgraph.graph import START, END, StateGraph
from typing_extensions import TypedDict


# --------------------------------------------------------------------------- #
# Estado partilhado entre todos os nós do grafo.
# --------------------------------------------------------------------------- #
class AgentState(TypedDict):
    """Estado que flui pelo StateGraph, partilhado por todos os agentes."""

    repo_path: str            # caminho local absoluto do repositório alvo
    bug_description: str      # descrição do bug, proveniente do Analisador
    issue_number: int         # número da issue no GitHub que originou este ciclo
    branch_name: str | None   # branch corrente; criada pelo gestor de issues
    test_results: str         # output capturado da última run de pytest
    retry_count: int          # quantas vezes o revisor rejeitou (0..3)
    status: str               # fase corrente do ciclo


# --------------------------------------------------------------------------- #
# Nó 4 — Revisor e Testador (Eduardo)
# --------------------------------------------------------------------------- #
def eduardo_reviewer_node(state: AgentState) -> AgentState:
    """Revisa a implementação e corre os testes num ambiente isolado.

    Lança ``pytest`` via ``subprocess`` dentro de ``repo_path``.  O
    processo filho corre isolado (cwd distinto do orquestrador) e não
    partilha state mutável.

    - returncode 0  -> status = "tests_passed"
    - returncode !=0 -> status = "tests_failed" e retry_count += 1
    """
    repo_path: str = state["repo_path"]

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=300,
    )

    state["test_results"] = result.stdout + result.stderr

    if result.returncode == 0:
        state["status"] = "tests_passed"
    else:
        state["status"] = "tests_failed"
        state["retry_count"] += 1  # tentativa extra para o programador

    return state


# --------------------------------------------------------------------------- #
# Nós-stub dos colegas (preencher com as implementações reais).               #
# --------------------------------------------------------------------------- #
def guidyanne_analyzer_node(state: AgentState) -> AgentState:
    """Agente 1 (Guidyanne) — Analisador de Código.

    TODO (Guidyanne): analisar ``repo_path`` à procura de código falhado,
    reproduzir o bug, gerar um ``BugReport`` (ver ``issue_manager/models.py``)
    e colocar a descrição em ``state["bug_description"]``.

    Entradas:  state["repo_path"]
    Saídas:    state["bug_description"], state["status"]
    """
    return {**state, "status": "analyzed"}


def carlos_issue_node(state: AgentState) -> AgentState:
    """Agente 2 (Carlos) — Gestor de Issues.

    TODO (Carlos): a partir de ``bug_description`` criar ou deduplicar uma
    issue no GitHub (``issue_manager``), criar a branch indicada e escrever
    o número real da issue em ``state["issue_number"]``.

    Entradas:  state["bug_description"], state["repo_path"]
    Saídas:    state["issue_number"], state["branch_name"], state["status"]
    """
    return {**state, "issue_number": state["issue_number"], "status": "issue_created"}


def ruben_programmer_node(state: AgentState) -> AgentState:
    """Agente 3 (Ruben) — Programador.

    TODO (Ruben): fazer checkout de ``branch_name`` e implementar a
    correção descrita em ``bug_description``.  Garantir que os testes
    relevantes passam antes de devolver o controlo ao revisor.

    Entradas:  state["repo_path"], state["branch_name"], state["bug_description"]
    Saídas:    state["status"]
    """
    return {**state, "status": "programmed"}


def pr_creation_node(state: AgentState) -> AgentState:
    """Passo final — cria o Pull Request no GitHub.

    TODO: integrar com a API do GitHub (``gh`` CLI ou ``requests``).
    Abre um PR a partir de ``branch_name`` para ``main``, linka a issue
    ``#issue_number`` e regista o resultado em ``state["status"]``.
    """
    return {**state, "status": "pr_created"}


# --------------------------------------------------------------------------- #
# Roteamento condicional após o revisor.
# --------------------------------------------------------------------------- #
def should_retry_or_pr(state: AgentState) -> str:
    """Decide o próximo passo após a fase de testes do revisor.

    - testes passaram           -> "create_pr"
    - testes falharam, < 3 tries -> "retry_programming"  (volta ao programador)
    - 3 tentativas esgotadas     -> "stop"               (encerra limpo)
    """
    if state["status"] == "tests_passed":
        return "create_pr"

    # status == "tests_failed"
    if state["retry_count"] >= 3:
        return "stop"
    return "retry_programming"


# --------------------------------------------------------------------------- #
# Orquestrador Central — StateGraph.
# --------------------------------------------------------------------------- #
def build_graph() -> StateGraph:
    """Constrói e devolve o StateGraph orquestrador (ainda não compilado)."""
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


# grafo compilado: o limite de recursão de segurança (recursion_limit=50)
# é passado a cada invoke() via config, conforme exigem as APIs do LangGraph.
orchestrator: Any = build_graph().compile()


# --------------------------------------------------------------------------- #
# Entrada de linha de comandos.
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    """ Executa o orquestrador sobre um repositório e bug dados.

        python -m orquestrador <repo_path> "<bug_description>" <issue_number>
    """
    if len(argv) != 4:
        print(__doc__)
        return 2

    repo_path, bug_description, issue_number = argv[1], argv[2], int(argv[3])

    initial_state: AgentState = {
        "repo_path": repo_path,
        "bug_description": bug_description,
        "issue_number": issue_number,
        "branch_name": None,
        "test_results": "",
        "retry_count": 0,
        "status": "ready",
    }

    final_state = orchestrator.invoke(
        initial_state, config={"recursion_limit": 50}
    )

    print("=== Resultado final ===")
    print(f"status        : {final_state['status']}")
    print(f"branch_name   : {final_state['branch_name']}")
    print(f"retry_count   : {final_state['retry_count']}")
    print(f"test_results  : {final_state['test_results'][:500]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
