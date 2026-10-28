"""Parser da saída do pytest: extrai falhas, resumo e tracebacks.

O parser é intencionalmente baseado em regex/linha-a-linha (sem depender do
plugin pytest-json) para funcionar em qualquer projeto sem configuração extra.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from agente_analisador.schemas import Failure, Summary

# Linha de cabeçalho de falha: "_______ test_name _______"
_FAIL_HEADER = re.compile(r"^_{5,}\s+(?P<name>.+?)\s+_{5,}$")

# "FAILED tests/test_foo.py::test_bar - AssertionError: ..." (pytest <9)
# ou "FAILED tests/test_foo.py::test_bar - assert ..." (pytest 9.x, sem tipo)
_FAILED_LINE = re.compile(
    r"^FAILED\s+(?P<test_id>[^\s]+)::(?P<test_name>[^\s]+)"
    r"(?:\s+-\s+(?P<error_message>.*))?$"
)

# Resumo final: "===== 2 failed, 8 passed, 1 skipped in 3.45s ====="
_SUMMARY = re.compile(
    r"(?:(?P<failed>\d+)\s+failed,?\s*)?"
    r"(?:(?P<passed>\d+)\s+passed,?\s*)?"
    r"(?:(?P<errors>\d+)\s+errors?,?\s*)?"
    r"(?:(?P<skipped>\d+)\s+skipped,?\s*)?"
    r"in\s+(?P<duration>[\d.]+)s"
)

# "tests/test_foo.py:42: AssertionError"  (sem mensagem)
# ou "tests/test_foo.py:42: AssertionError: assert ..."  (com mensagem)
# ou "C:\...\test_foo.py:42: AssertionError"  (Windows absoluto, com ':')
# Usa '.+?' não-greedy para que o ficheiro englobe paths com ':' (drive letter).
_LOCATION = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):\s*"
    r"(?P<error_type>[A-Za-z_][\w.]*)"
    r"(?::\s*(?P<error_message>.*))?$"
)

# "E   assert 1 == 2"
_ASSERT_LINE = re.compile(r"^E\s+(?P<msg>.+)$")


def parse_failures(stdout: str, repo_path: str) -> list[Failure]:
    """Extrai a lista de falhas a partir da saída do pytest.

    Estratégia:
      1. Procura linhas `FAILED ...` para identificar testes falhados.
      2. Para cada um, tenta localizar o traceback correspondente
         (cabeçalho `_______ test_name _______`) e extrair:
           - ficheiro/linha (linha `file:line: ErrorType: message`)
           - tipo de erro e mensagem
           - traceback completo (bloco até à próxima linha `=====`).
      3. Gera passos de reprodução determinísticos.
    """
    failures: list[Failure] = []

    # Mapa test_id -> dados da linha FAILED
    failed_map: dict[str, dict[str, str | None]] = {}
    for line in stdout.splitlines():
        m = _FAILED_LINE.match(line)
        if m:
            # O nodeid do pytest pode ser:
            #   file::test_name               (função)
            #   file::Class::test_name         (método de classe)
            #   file::Class::test_name[params] (parametrizado)
            # O regex captura `test_id` = tudo até ao último `::` e
            # `test_name` = último segmento. Por isso voltamos a partir o
            # `test_id` para extrair o ficheiro real (primeiro segmento).
            raw_id = m["test_id"]  # ex.: "tests/x.py::TestFoo"
            raw_name = m["test_name"]  # ex.: "test_bar[case-1]"
            full_test_id = f"{raw_id}::{raw_name}"
            # O ficheiro é tudo antes do primeiro "::".
            file_only = raw_id.split("::", 1)[0]
            # O nome do teste é o último segmento (sem parâmetros).
            test_name_only = raw_name.split("[", 1)[0]
            failed_map[full_test_id] = {
                "file": file_only,
                "test_name": test_name_only,
                "error_message": m["error_message"],
            }

    # Se não há linhas FAILED (ex.: pytest muito antigo), sai vazio.
    if not failed_map:
        # fallback: procura só cabeçalhos de falha
        for line in stdout.splitlines():
            m = _FAIL_HEADER.match(line)
            if m:
                name = m["name"].strip()
                # Tenta extrair test_id do nome (pode incluir params)
                failures.append(
                    Failure(
                        test_id=name,
                        file="",
                        test_name=name.split("[")[0],
                        error_type="Unknown",
                        error_message="Falha capturada sem detalhes estruturados.",
                        traceback="",
                        reproduction_steps=_repro_steps(repo_path, "", name),
                    )
                )
        return failures

    # Para cada falha conhecida, extrair traceback e localização detalhada.
    lines = stdout.splitlines()
    for test_id, info in failed_map.items():
        file_path = str(info["file"])
        test_name = str(info["test_name"])
        error_type = "Unknown"
        error_message = str(info["error_message"] or "")
        line_no: int | None = None
        traceback_text = ""

        # Procura o cabeçalho do traceback correspondente.
        # O cabeçalho pode ser "_______ test_name[params] _______".
        header_idx = _find_header_index(lines, test_name)
        if header_idx is not None:
            block = _extract_traceback_block(lines, header_idx)
            traceback_text = "\n".join(block)
            loc = _find_location_in_block(block)
            if loc:
                line_no = loc["line"]
                if loc["error_type"]:
                    error_type = loc["error_type"]
                if loc["error_message"]:
                    error_message = loc["error_message"]
                # Se a linha FAILED não trouxe mensagem, usa o assert do traceback.
                elif not error_message:
                    error_message = _extract_assert_message(block) or error_message

        failures.append(
            Failure(
                test_id=test_id,
                file=file_path,
                test_name=test_name,
                line=line_no,
                error_type=error_type,
                error_message=error_message.strip(),
                traceback=traceback_text,
                reproduction_steps=_repro_steps(repo_path, file_path, test_name),
            )
        )

    return failures


def _find_header_index(lines: list[str], test_name: str) -> int | None:
    """Encontra o índice do cabeçalho do traceback correspondente ao teste.

    O cabeçalho do pytest pode ter várias formas:
      - function:  `_______ test_name[params] _______`
      - classe:     `_______ TestClass.test_name[params] _______`
      - método:     `_______ TestClass.test_name[params-1] _______`

    Por isso procuramos um cabeçalho cujo nome:
      - termine em `.test_name` (classe), ou
      - seja exatamente `test_name` (função),
    sempre a ignorar a parte dos parâmetros `[...]`.
    """
    target = test_name.split("[", 1)[0]
    for i, line in enumerate(lines):
        m = _FAIL_HEADER.match(line)
        if not m:
            continue
        name = m["name"].strip().split("[", 1)[0]
        if name == target or name.endswith(f".{target}"):
            return i
    return None


def _extract_traceback_block(lines: list[str], start: int) -> list[str]:
    """Extrai o bloco de traceback desde `start` até à próxima linha `=====`."""
    block: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("====") or (
            line.startswith("----") and line.endswith("----")
        ):
            break
        block.append(line)
        # Segurança: parar em blocos muito grandes.
        if len(block) > 500:
            block = block[:500]
            break
    return block


def _find_location_in_block(block: Iterable[str]) -> dict[str, str | int | None] | None:
    """Procura dentro do bloco por uma linha `file:line: ErrorType: message`."""
    for line in block:
        m = _LOCATION.match(line.strip())
        if m:
            return {
                "file": m["file"],
                "line": int(m["line"]) if m["line"].isdigit() else None,
                "error_type": m["error_type"],
                "error_message": m["error_message"],
            }
    return None


def _extract_assert_message(block: Iterable[str]) -> str | None:
    """Extrai a primeira linha `E   <mensagem>` do traceback (assert visível)."""
    for line in block:
        m = _ASSERT_LINE.match(line.rstrip("\n"))
        if m:
            return m["msg"].strip()
    return None


def parse_summary(stdout: str) -> Summary:
    """Extrai o resumo agregado da última linha `===== N failed, M passed... =====`."""
    summary = Summary()
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if line.startswith("=") and ("passed" in line or "failed" in line or "error" in line):
            m = _SUMMARY.search(line)
            if m:
                summary.failed = int(m["failed"] or 0)
                summary.passed = int(m["passed"] or 0)
                summary.errors = int(m["errors"] or 0)
                summary.skipped = int(m["skipped"] or 0)
                summary.total = (
                    summary.passed + summary.failed + summary.errors + summary.skipped
                )
                summary.duration_seconds = float(m["duration"] or 0.0)
                return summary
    return summary


def _repro_steps(repo_path: str, file_path: str, test_name: str) -> list[str]:
    """Gera passos de reprodução determinísticos e executáveis."""
    steps = [f"cd {repo_path}"]
    if file_path and test_name:
        # Limpa parâmetros de testes parametrizados: test_foo[case-1] -> "test_foo[case-1]"
        # O pytest aceita os parênteses retos tal qual.
        steps.append(f"pytest {file_path}::{test_name} -v --tb=long")
    elif file_path:
        steps.append(f"pytest {file_path} -v --tb=long")
    else:
        steps.append("pytest -v --tb=long")
    return steps
