"""Executa o pytest num repositório local via subprocess.

Isolado num módulo próprio para facilitar testes (mock de `subprocess.run`)
e reutilização por outros agentes.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


class PytestNotFoundError(RuntimeError):
    """Lançada quando o executável `pytest` não está disponível."""


@dataclass(frozen=True)
class PytestRun:
    """Resultado bruto de uma execução de pytest."""

    returncode: int
    stdout: str
    stderr: str
    cmd: list[str]


def _resolve_pytest() -> str:
    """Encontra o executável pytest no PATH; levanta erro se não existir."""
    pytest_path = shutil.which("pytest") or shutil.which("pytest.exe")
    if not pytest_path:
        raise PytestNotFoundError(
            "pytest não encontrado no PATH. Instale com `pip install pytest`."
        )
    return pytest_path


def run_pytest(
    repo_path: str,
    pytest_args: list[str] | None = None,
    *,
    timeout: int = 600,
    env: dict[str, str] | None = None,
) -> PytestRun:
    """Executa `pytest` no `repo_path` e devolve a saída capturada.

    Args:
        repo_path: Caminho do repositório onde correr o pytest.
        pytest_args: Argumentos extra a passar ao pytest (ex.: ["-x", "--tb=short"]).
        timeout: Tempo máximo de execução em segundos.
        env: Variáveis de ambiente (default: herdadas do processo).

    Returns:
        PytestRun com returncode, stdout, stderr e comando executado.
    """
    pytest_exec = _resolve_pytest()
    cmd = [pytest_exec, *(pytest_args or []), "--tb=long", "-v", "-rA"]

    # Força UTF-8 no subprocess do pytest para que tracebacks com acentos
    # (ex.: docstrings em PT) sejam descodificados corretamente, independentemente
    # do encoding da consola (cp1252 no Windows PT, por exemplo).
    import os as _os

    child_env = dict(_os.environ)
    child_env["PYTHONIOENCODING"] = "utf-8"
    if env is not None:
        child_env.update(env)

    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=child_env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"pytest excedeu o timeout de {timeout}s.") from exc

    return PytestRun(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmd=cmd,
    )
