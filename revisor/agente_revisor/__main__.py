"""Entry-point CLI: `python -m agente_revisor`."""

from __future__ import annotations

import argparse
import io
import sys
from collections.abc import Sequence

from agente_revisor.agent import RevisorAgent


def _ensure_utf8_stdout() -> None:
    """Garante que stdout/stderr usam UTF-8, mesmo em consolas Windows (cp1252).

    Isto e essencial para que o JSON de saida (que pode conter acentos nos
    tracebacks/docstrings dos testes) seja valido e parseable por qualquer
    consumidor downstream.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        encoding = getattr(stream, "encoding", None) or ""
        if encoding.lower().replace("-", "") != "utf8":
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            except (AttributeError, ValueError):
                # Fallback: envolve num TextIOWrapper UTF-8 (Python <3.7 ou pipes).
                setattr(sys, stream_name, io.TextIOWrapper(
                    stream.buffer, encoding="utf-8", errors="replace",
                    line_buffering=True,
                ))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agente-revisor",
        description="Executa pytest num repositorio e devolve erros em JSON estruturado.",
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Caminho do repositorio onde executar o pytest.",
    )
    parser.add_argument(
        "--pytest-args",
        nargs="*",
        default=[],
        help="Argumentos extra a passar ao pytest (ex.: -x --tb short).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Timeout em segundos (default: 600).",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indentacao do JSON de saida (default: 2).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _ensure_utf8_stdout()
    parser = _build_parser()
    args = parser.parse_args(argv)

    agent = RevisorAgent()
    state = {
        "repo_path": args.repo,
        "pytest_args": args.pytest_args,
        "timeout": args.timeout,
    }

    try:
        out = agent.run(state)
    except ValueError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    result = out["revisor_result"]
    print(result.model_dump_json(indent=args.indent))
    # Exit code espelha o do pytest quando possivel.
    if result.status == "passed":
        return 0
    if result.status == "no_tests":
        return 5
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
