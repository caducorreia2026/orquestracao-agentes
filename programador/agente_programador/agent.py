"""Agente Programador: aplica correções de código numa branch Git isolada.

Recebe o caminho do repositório, o ID da issue, o ficheiro com o bug e uma
descrição do problema; cria a branch `fix/issue-{id}`, lê o ficheiro, aplica a
correção (via callable injetável `fixer`) e confirma tudo num commit automático.

O contrato de estado é simples:

    Entrada (state):
        {
            "repo_path": str,                 # obrigatório
            "issue_id": str,                  # obrigatório
            "file_path": str,                 # obrigatório (relativo ao repo ou absoluto)
            "problem_description": str,       # obrigatório
            "old_code": str | None,           # opcional, usado pelo fixer por defeito
            "new_code": str | None,           # opcional, usado pelo fixer por defeito
            "commit_message": str | None,     # opcional, gera uma por defeito
            "author_name": str | None,        # opcional
            "author_email": str | None,       # opcional
        }

    Saída (merge no estado):
        {
            "programador_result": ProgramadorResult,
            "messages": [ <mensagem system com JSON do resultado> ],
        }

O fixer real (que decide como corrigir o código a partir da descrição) é
provido pelo orquestrador — pode ser um LLM, uma heurística, etc. O fixer por
defeito faz uma substituição textual (`old_code` -> `new_code`) e exige que
ambos sejam fornecidos no estado.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from typing import Any

from git import Actor, Repo
from git.exc import GitCommandError
from pydantic import ValidationError

from agente_programador.schemas import ProgramadorResult

logger = logging.getLogger(__name__)


# Tipo do callable que transforma o código.
# Recebe (file_path, current_content, problem_description, state) e devolve o
# novo conteúdo do ficheiro.
Fixer = Callable[[str, str, str, Mapping[str, Any]], str]


def _default_fixer(
    file_path: str,
    current_content: str,
    problem_description: str,
    state: Mapping[str, Any],
) -> str:
    """Fixer por defeisto: substituição textual de `old_code` por `new_code`.

    Levanta `ValueError` se as chaves `old_code`/`new_code` não estiverem no
    estado — nesse caso o consumidor deve injetar um fixer próprio (ex.: LLM).
    """
    old_code = state.get("old_code")
    new_code = state.get("new_code")
    if old_code is None or new_code is None:
        raise ValueError(
            "O fixer por defeito exige `old_code` e `new_code` no estado. "
            "Passe um `fixer` customizado ao ProgramadorAgent para corrigir "
            "código a partir da descrição livre do problema."
        )
    if old_code not in current_content:
        logger.warning(
            "old_code não encontrado em %s; a substituição não alterou o ficheiro.",
            file_path,
        )
        return current_content
    return current_content.replace(old_code, new_code, 1)


def _resolve_file_path(repo: Repo, file_path: str) -> str:
    """Converte o caminho do ficheiro para um caminho absoluto dentro do repo."""
    if os.path.isabs(file_path):
        return os.path.abspath(file_path)
    # Usa o working tree do repo como base para caminhos relativos.
    return os.path.join(repo.working_tree_dir or os.getcwd(), file_path)


def _default_commit_message(issue_id: str, file_path: str, description: str) -> str:
    """Gera uma mensagem de commit clara e concisa."""
    short_desc = description.strip().splitlines()[0] if description.strip() else "correção"
    return f"fix: resolve issue #{issue_id} — {short_desc} ({file_path})"


class ProgramadorAgent:
    """Agente que corrige um ficheiro dentro de uma branch Git isolada.

    Exemplo:
        >>> agent = ProgramadorAgent()
        >>> state = {
        ...     "repo_path": "/caminho/ao/repo",
        ...     "issue_id": "42",
        ...     "file_path": "src/calc.py",
        ...     "problem_description": "divisão por zero quando input é 0",
        ...     "old_code": "return a / b",
        ...     "new_code": "if b == 0: raise ValueError('...')\\nreturn a / b",
        ... }
        >>> out = agent.run(state)
        >>> print(out["programador_result"].model_dump_json(indent=2))
    """

    def __init__(
        self,
        *,
        fixer: Fixer = _default_fixer,
        repo_cls: type[Repo] = Repo,
    ) -> None:
        # `fixer` é injetável para facilitar testes e para plugar um LLM.
        # `repo_cls` é injetável para permitir mock da API gitpython.
        self._fixer = fixer
        self._repo_cls = repo_cls

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Executa o ciclo completo: branch -> lê -> corrige -> commit."""
        repo_path = state.get("repo_path")
        issue_id = state.get("issue_id")
        file_path = state.get("file_path")
        problem_description = state.get("problem_description")

        if not repo_path:
            raise ValueError("`state['repo_path']` é obrigatório.")
        if not issue_id:
            raise ValueError("`state['issue_id']` é obrigatório.")
        if not file_path:
            raise ValueError("`state['file_path']` é obrigatório.")
        if not problem_description:
            raise ValueError("`state['problem_description']` é obrigatório.")

        repo_path = os.fspath(repo_path)
        issue_id = str(issue_id)
        branch_name = f"fix/issue-{issue_id}"

        logger.info("Programador: issue #%s em %s", issue_id, repo_path)

        try:
            repo = self._repo_cls(repo_path)
        except (GitCommandError, ValueError) as exc:
            logger.error("Repositório inválido %s: %s", repo_path, exc)
            return self._wrap(
                ProgramadorResult(
                    repo_path=repo_path,
                    issue_id=issue_id,
                    branch=branch_name,
                    file_path=file_path,
                    changed=False,
                    commit_message="",
                    error=f"Repositório inválido: {exc}",
                )
            )

        abs_path = _resolve_file_path(repo, file_path)
        rel_path = os.path.relpath(abs_path, repo.working_tree_dir or os.getcwd())

        # 1. Cria / muda para a branch isolada.
        try:
            self._checkout_branch(repo, branch_name)
        except GitCommandError as exc:
            logger.error("Falha ao criar/checkout da branch %s: %s", branch_name, exc)
            return self._wrap(
                ProgramadorResult(
                    repo_path=repo_path,
                    issue_id=issue_id,
                    branch=branch_name,
                    file_path=rel_path,
                    changed=False,
                    commit_message="",
                    error=f"Falha ao criar/checkout da branch: {exc}",
                )
            )

        # 2. Lê o conteúdo atual do ficheiro.
        try:
            with open(abs_path, "r", encoding="utf-8") as fh:
                current_content = fh.read()
        except FileNotFoundError as exc:
            logger.error("Ficheiro não encontrado %s", abs_path)
            return self._wrap(
                ProgramadorResult(
                    repo_path=repo_path,
                    issue_id=issue_id,
                    branch=branch_name,
                    file_path=rel_path,
                    changed=False,
                    commit_message="",
                    error=f"Ficheiro não encontrado: {abs_path}",
                )
            )

        # 3. Corrige o código via fixer injetável.
        try:
            new_content = self._fixer(
                rel_path, current_content, problem_description, state
            )
        except Exception as exc:  # noqa: BLE001 — fixer pode levantar por defeito
            logger.error("Fixer falhou: %s", exc)
            return self._wrap(
                ProgramadorResult(
                    repo_path=repo_path,
                    issue_id=issue_id,
                    branch=branch_name,
                    file_path=rel_path,
                    changed=False,
                    commit_message="",
                    error=f"Fixer falhou: {exc}",
                )
            )

        changed = new_content != current_content

        # 4. Guarda o ficheiro (mesmo que não haja alteração para garantir
        #    consistência do working tree antes do commit).
        with open(abs_path, "w", encoding="utf-8") as fh:
            fh.write(new_content)

        # 5. Commit automático (apenas se houve alteração).
        commit_message = state.get("commit_message") or _default_commit_message(
            issue_id, rel_path, problem_description
        )
        commit_hash: str | None = None
        if changed:
            try:
                commit_hash = self._commit_file(
                    repo, rel_path, commit_message, state
                )
                logger.info(
                    "Programador: commit %s na branch %s", commit_hash[:8], branch_name
                )
            except GitCommandError as exc:
                logger.error("Falha no commit: %s", exc)
                return self._wrap(
                    ProgramadorResult(
                        repo_path=repo_path,
                        issue_id=issue_id,
                        branch=branch_name,
                        file_path=rel_path,
                        changed=changed,
                        commit_message=commit_message,
                        error=f"Falha no commit: {exc}",
                    )
                )
        else:
            logger.info("Programador: nenhuma alteração detectada; sem commit.")

        return self._wrap(
            ProgramadorResult(
                repo_path=repo_path,
                issue_id=issue_id,
                branch=branch_name,
                file_path=rel_path,
                changed=changed,
                commit=commit_hash,
                commit_message=commit_message,
            )
        )

    # -- helpers de Git (injetáveis via `repo_cls` para testes) ----

    @staticmethod
    def _checkout_branch(repo: Repo, branch_name: str) -> None:
        """Cria a branch se não existir e muda para ela."""
        if branch_name in repo.heads:
            repo.git.checkout(branch_name)
        else:
            repo.git.checkout("-b", branch_name)

    @staticmethod
    def _commit_file(
        repo: Repo,
        rel_path: str,
        message: str,
        state: Mapping[str, Any],
    ) -> str:
        """Stageia o ficheiro e cria um commit, devolvendo o seu hash."""
        repo.index.add([rel_path])
        author: Actor | None = None
        name = state.get("author_name")
        email = state.get("author_email")
        if name or email:
            author = Actor(name or "agente-programador", email or "agente@local")
        commit = repo.index.commit(message, author=author, committer=author)
        return commit.hexsha

    # -- integração LangGraph ----

    def as_node(self) -> Callable[[dict[str, Any]], dict[str, Any]]:
        """Devolve uma função compatível com um nó LangGraph.

        Uso:
            graph.add_node("programador", ProgramadorAgent().as_node())
        """

        def _node(state: dict[str, Any]) -> dict[str, Any]:
            return self.run(state)

        _node.__name__ = "programador_node"
        return _node

    @staticmethod
    def _wrap(result: ProgramadorResult) -> dict[str, Any]:
        """Empacota o resultado no formato esperado pelo estado LangGraph."""
        return {
            "programador_result": result,
            "messages": [result.to_langgraph_message()],
        }


__all__ = ["ProgramadorAgent", "Fixer", "_default_fixer"]
