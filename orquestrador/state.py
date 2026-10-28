"""Definição do estado partilhado do Orquestrador.

O ``AgentState`` é o contrato de dados que flui pelo StateGraph do LangGraph
entre todos os agentes.  Cada nó lê e/ou escreve chaves deste dicionário
partilhado.

Todas as chaves são obrigatórias (TypedDict sem ``total=False``) para garantir
que nenhum agente aceda a uma chave inexistente.  Valores ``None`` marcam
campos que ainda não foram preenchidos por nenhum agente.
"""
from __future__ import annotations

from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Estado imutável por valor, mutável por referência no fluxo do grafo.

    Campos:
        repo_path:       Caminho absoluto do repositório alvo no disco.
        bug_description: Texto livre descrevendo o bug (do Analisador).
        issue_number:    Número da issue no GitHub que originou este ciclo.
        branch_name:     Nome da branch de trabalho; criada pelo gestor de
                         issues e usada pelo programador.
        test_results:    Output capturado da última run de pytest (stdout+stderr).
        retry_count:     Número de tentativas falhas do ciclo programador->revisor.
        status:          Fase corrente do ciclo (ex.: "tests_passed",
                         "tests_failed", "issue_created", "pr_created").
    """

    repo_path: str
    bug_description: str
    issue_number: int
    branch_name: str | None
    test_results: str
    retry_count: int
    status: str


__all__ = ["AgentState"]