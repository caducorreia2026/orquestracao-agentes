"""Entry point CLI do Orquestrador.

Uso:
    python -m orquestrador <repo_path> "<bug_description>" <issue_number>
"""
from __future__ import annotations

import sys

from orquestrador.graph import orchestrator
from orquestrador.state import AgentState


def main(argv: list[str]) -> int:
    """Executa o orquestrador sobre um repositório e bug dados."""
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
