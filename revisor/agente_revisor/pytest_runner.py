"""Executa o pytest num repositorio local via subprocess.

Isolado neste modulo para facilitar testes (mock de ``subprocess.run``) e
reutilizacao por outros agentes.

O runner usa ``python -m pytest`` (em vez de ``pytest`` directo) para garantir
que o interprete correcto e usado, e captura stdout/stderr como texto UTF-8.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass


class PytestNotFoundError(RuntimeError):
    """Lancada quando o modulo pytest nao esta instalado no interprete activo."""


@dataclass(frozen=True)
class PytestRun:
    """Resultado bruto de uma execucao de pytest."""

    returncode: int
    stdout: str
    stderr: str
    cmd: list[str]


def _check_pytest_available() -> None:
    """Verifica se o modulo pytest pode ser carregado pelo interprete activo.

    Usa ``import pytest`` em vez de ``shutil.which`` porque, em alguns
    ambientes (notavelmente Windows), o script executavel ``pytest`` nao
    existe no PATH mas o modulo Python e importavel normalmente.
    """
    try:
        import pytest as _pytest  # noqa: F401
    except ImportError as exc:
        raise PytestNotFoundError(
            "pytest nao encontrado. Instale com `pip install pytest`."
        ) from exc


def _build_cmd(pytest_args: list[str] | None) -> list[str]:
    """Constrói o comando ``python -m pytest`` com os argumentos padrao."""
    cmd = [sys.executable, "-m", "pytest"]
    if pytest_args:
        cmd.extend(pytest_args)
    cmd.extend(["--tb=long", "-v", "-rA"])
    return cmd


def _make_child_env(env: dict[str, str] | None) -> dict[str, str]:
    """Constrói o ambiente para o processo filho, forçando UTF-8."""
    import os as _os

    child_env = dict(_os.environ)
    child_env["PYTHONIOENCODING"] = "utf-8"
    if env is not None:
        child_env.update(env)
    return child_env


def run_pytest(
    repo_path: str,
    pytest_args: list[str] | None = None,
    *,
    timeout: int = 600,
    env: dict[str, str] | None = None,
) -> PytestRun:
    """Executa pytest no repo_path e devolve a saida capturada.

    Args:
        repo_path: Caminho do repositorio onde correr o pytest.
        pytest_args: Argumentos extra a passar ao pytest (ex.: ["-x", "--tb=short"]).
        timeout: Tempo maximo de execucao em segundos.
        env: Variaveis de ambiente (default: herdadas do processo).

    Returns:
        PytestRun com returncode, stdout, stderr e comando executado.

    Raises:
        PytestNotFoundError: se o modulo pytest nao estiver instalado.
        TimeoutError: se o pytest exceder o timeout.
    """
    _check_pytest_available()
    cmd = _build_cmd(pytest_args)
    child_env = _make_child_env(env)

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


# Runner injetavel de pytest — isola subprocess para facilitar testes.
# Usa python -m pytest para garantir que o interprete correcto corre o pytest
# dentro do venv activo, tambem quando o script executavel nao esta no PATH.
class PytestRunner:
    """Runner injetavel de pytest — isola subprocess para facilitar testes.

    Exemplo:
        >>> runner = PytestRunner()
        >>> out = runner.run("/caminho/ao/repo")
        >>> out.returncode
        0
    """

    def __init__(self, *, timeout: int = 300) -> None:
        self._timeout = timeout

    def run(
        self, repo_path: str, pytest_args: list[str] | None = None
    ) -> PytestRun:
        """Lanca pytest de forma isolada dentro de repo_path.

        O processo filho corre com cwd=repo_path, o que isola a pasta de
        trabalho. stdout e stderr sao capturados e devolvidos juntos.
        """
        _check_pytest_available()
        cmd = _build_cmd(pytest_args)
        child_env = _make_child_env(None)

        try:
            proc = subprocess.run(
                cmd,
                cwd=repo_path,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._timeout,
                env=child_env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                f"pytest excedeu o timeout de {self._timeout}s."
            ) from exc

        return PytestRun(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmd=cmd,
        )


__all__ = ["PytestRun", "PytestRunner", "PytestNotFoundError", "run_pytest"]
