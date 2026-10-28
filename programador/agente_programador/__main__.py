"""Entry-point CLI: `python -m agente_programador`."""

from __future__ import annotations

import argparse
import io
import sys
from collections.abc import Sequence

from agente_programador.agent import ProgramadorAgent


def _ensure_utf8_stdout() -> None:
    """Garante que stdout/stderr usam UTF-8, mesmo em consolas Windows (cp1252)."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        encoding = getattr(stream, "encoding", None) or ""
        if encoding.lower().replace("-", "") != "utf8":
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            except (AttributeError, ValueError):
                setattr(sys, stream_name, io.TextIOWrapper(
                    stream.buffer, encoding="utf-8", errors="replace",
                    line_buffering=True,
                ))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agente-programador",
        description="Aplica uma correção de código numa branch Git isolada.",
    )
    parser.add_argument("--repo", required=True, help="Caminho do repositório Git.")
    parser.add_argument("--issue-id", required=True, help="ID da issue (ex.: 42).")
    parser.add_argument("--file", required=True, help="Ficheiro a corrigir (relativo ao repo).")
    parser.add_argument("--problem", required=True, help="Descrição do problema.")
    parser.add_argument(
        "--old-code", default=None,
        help="Snippet atual a substituir (fixer por defeito).",
    )
    parser.add_argument(
        "--new-code", default=None,
        help="Snippet corrigido (fixer por defeito).",
    )
    parser.add_argument("--commit-message", default=None, help="Mensagem de commit.")
    parser.add_argument("--author-name", default=None, help="Nome do autor do commit.")
    parser.add_argument("--author-email", default=None, help="Email do autor do commit.")
    parser.add_argument(
        "--indent", type=int, default=2, help="Indentação do JSON de saída (default: 2).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _ensure_utf8_stdout()
    parser = _build_parser()
    args = parser.parse_args(argv)

    state = {
        "repo_path": args.repo,
        "issue_id": args.issue_id,
        "file_path": args.file,
        "problem_description": args.problem,
        "old_code": args.old_code,
        "new_code": args.new_code,
        "commit_message": args.commit_message,
        "author_name": args.author_name,
        "author_email": args.author_email,
    }

    agent = ProgramadorAgent()
    try:
        out = agent.run(state)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    result = out["programador_result"]
    print(result.model_dump_json(indent=args.indent))
    if result.error:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
