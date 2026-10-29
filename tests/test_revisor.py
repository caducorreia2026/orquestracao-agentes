"""Testes do Agente Revisor.

Estrategia:
  - Testes do parser usam strings de exemplo (rapidos, deterministas).
  - Testes do formatter validam status, truncamento e serializacao.
  - Testes do agente usam runner mockado (sem subprocess).
  - Teste end-to-end corre o pytest real num repo temporario.
"""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import pytest

from agente_revisor.agent import RevisorAgent
from agente_revisor.error_parser import parse_failures, parse_summary
from agente_revisor.formatter import build_result
from agente_revisor.pytest_runner import PytestRun

# ---------------------------------------------------------------------------
# Fixtures / dados de exemplo
# ---------------------------------------------------------------------------

SAMPLE_STDOUT = textwrap.dedent(
    """\
    ============================= test session starts ==============================
    platform linux -- Python 3.11.0
    collected 3 items

    tests/test_calc.py .F.                                                   [100%]

    =================================== FAILURES ===================================
    _________________________ test_subtract_fails _________________________
    def test_subtract_fails():
    >       assert 2 - 2 == 5
    tests/test_calc.py:5: AssertionError
    E       assert (2 - 2) == 5
    E        +  where 2 - 2 = 0
    ----------------------------- Captured stdout call -----------------------------
    nada
    ============================== 1 failed, 2 passed in 0.05s ===============================
    FAILED tests/test_calc.py::test_subtract_fails - AssertionError: assert (2 - 2) == 5
    """
)

# Output com teste baseado em CLASSE (cabecalho "Class.test_name").
SAMPLE_STDOUT_CLASS = textwrap.dedent(
    """\
    ============================= test session starts ==============================
    platform linux -- Python 3.11.0
    collected 2 items

    tests/test_discount.py .F                                                [100%]

    =================================== FAILURES ===================================
    ____________________ TestDiscount.test_ten_percent ____________________
    self = <test_discount.TestDiscount object at 0x...>

        def test_ten_percent(self):
    >       assert calculate_discount(100.0, 10) == 90.0
    E       assert 1100.0 == 90.0
    E        +  where 1100.0 = calculate_discount(100.0, 10)

    tests\\test_discount.py:26: AssertionError
    ============================== 1 failed, 1 passed in 0.05s ===============================
    FAILED tests/test_discount.py::TestDiscount::test_ten_percent - assert 1100.0 == 90.0
    """
)


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Cria um mini-repositorio com testes que passam e falham."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tmp_path / "tests" / "test_calc.py").write_text(
        textwrap.dedent(
            """\
            def test_add_passes():
                assert 1 + 1 == 2

            def test_subtract_fails():
                assert 2 - 2 == 5

            def test_multiply_passes():
                assert 3 * 3 == 9
            """
        )
    )
    return tmp_path


@pytest.fixture
def fake_repo_class(tmp_path: Path) -> Path:
    """Repo com testes baseados em classes."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "__init__.py").write_text("")
    (tmp_path / "tests" / "test_discount.py").write_text(
        textwrap.dedent(
            """\
            def calculate_discount(price, rate):
                return price + price * rate  # bug intencional

            class TestDiscount:
                def test_passes(self):
                    assert calculate_discount(0, 0) == 0

                def test_ten_percent_fails(self):
                    assert calculate_discount(100.0, 10) == 90.0
            """
        )
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class TestParser:
    def test_parse_summary_extracts_counts(self) -> None:
        summary = parse_summary(SAMPLE_STDOUT)
        assert summary.failed == 1
        assert summary.passed == 2
        assert summary.total == 3
        assert summary.duration_seconds == pytest.approx(0.05, abs=0.01)

    def test_parse_failures_extracts_one_failure(self) -> None:
        failures = parse_failures(SAMPLE_STDOUT, repo_path="/repo")
        assert len(failures) == 1
        f = failures[0]
        assert f.test_id == "tests/test_calc.py::test_subtract_fails"
        assert f.file == "tests/test_calc.py"
        assert f.test_name == "test_subtract_fails"
        assert f.line == 5
        assert f.error_type == "AssertionError"
        assert "2 - 2" in f.error_message or "assert" in f.error_message

    def test_parse_failures_generates_repro_steps(self) -> None:
        failures = parse_failures(SAMPLE_STDOUT, repo_path="/repo")
        steps = failures[0].reproduction_steps
        assert steps[0] == "cd /repo"
        assert "pytest tests/test_calc.py::test_subtract_fails" in steps[1]

    def test_parse_failures_empty_on_clean_output(self) -> None:
        clean = "1 passed in 0.01s\n"
        assert parse_failures(clean, repo_path="/repo") == []

    def test_parse_summary_handles_no_tests(self) -> None:
        out = "no tests ran in 0.00s\n"
        summary = parse_summary(out)
        assert summary.total == 0

    def test_parse_failures_class_based_test(self) -> None:
        """Testes em classes: o ficheiro nao deve incluir o nome da classe."""
        failures = parse_failures(SAMPLE_STDOUT_CLASS, repo_path="/repo")
        assert len(failures) == 1
        f = failures[0]
        assert f.test_id == "tests/test_discount.py::TestDiscount::test_ten_percent"
        # O ficheiro NAO deve conter "::TestDiscount".
        assert f.file == "tests/test_discount.py"
        assert f.test_name == "test_ten_percent"
        assert f.line == 26
        assert f.error_type == "AssertionError"
        assert "1100.0" in f.error_message
        assert f.traceback  # nao vazio
        # Passos de reproducao usam apenas o nome do teste (sem classe).
        assert "test_ten_percent" in f.reproduction_steps[1]
        assert "::TestDiscount" not in f.reproduction_steps[1]


# ---------------------------------------------------------------------------
# Formatter
# ---------------------------------------------------------------------------

class TestFormatter:
    def test_build_result_passed(self) -> None:
        run = PytestRun(
            returncode=0,
            stdout="============================== 1 passed in 0.01s ===============================\n",
            stderr="",
            cmd=["pytest"],
        )
        result = build_result(repo_path="/repo", pytest_run=run)
        assert result.status == "passed"
        assert result.exit_code == 0
        assert result.failures == []
        assert result.summary.passed == 1

    def test_build_result_failed(self) -> None:
        run = PytestRun(
            returncode=1,
            stdout=SAMPLE_STDOUT,
            stderr="",
            cmd=["pytest"],
        )
        result = build_result(repo_path="/repo", pytest_run=run)
        assert result.status == "failed"
        assert result.exit_code == 1
        assert len(result.failures) == 1
        assert result.summary.failed == 1

    def test_build_result_no_tests(self) -> None:
        run = PytestRun(
            returncode=5,
            stdout="no tests ran in 0.00s\n",
            stderr="",
            cmd=["pytest"],
        )
        result = build_result(repo_path="/repo", pytest_run=run)
        assert result.status == "no_tests"

    def test_build_result_error_when_collection_error(self) -> None:
        """Quando ha erros de colecao e zero falhas, status = error."""
        stdout = (
            "============================= test session starts ==============================\n"
            "collected 0 items / 1 error\n"
            "====== ERRORS ======\n"
            "ERROR collecting tests/test_x.py - ImportError: no module\n"
            "!!!!!!!!!!!!!!!!!!! 1 error in 0.01s !!!!!!!!!!!!!!!!!!!"
        )
        run = PytestRun(returncode=2, stdout=stdout, stderr="", cmd=["pytest"])
        result = build_result(repo_path="/repo", pytest_run=run)
        assert result.status == "error"

    def test_build_result_truncates_huge_output(self) -> None:
        huge = "FAILED tests/x.py::y - AssertionError: boom\n" * 5000
        run = PytestRun(returncode=1, stdout=huge, stderr="", cmd=["pytest"])
        result = build_result(repo_path="/repo", pytest_run=run)
        assert len(result.raw_output) <= 20_000 + 50  # margem do sufixo

    def test_build_result_record_exit_code(self) -> None:
        run = PytestRun(
            returncode=1,
            stdout=SAMPLE_STDOUT,
            stderr="",
            cmd=["pytest"],
        )
        result = build_result(repo_path="/repo", pytest_run=run)
        assert result.exit_code == 1

    def test_result_serializes_to_valid_json(self) -> None:
        run = PytestRun(
            returncode=1,
            stdout=SAMPLE_STDOUT,
            stderr="",
            cmd=["pytest"],
        )
        result = build_result(repo_path="/repo", pytest_run=run)
        data = json.loads(result.model_dump_json())
        assert data["agent"] == "revisor"
        assert data["status"] == "failed"
        assert isinstance(data["failures"], list)
        assert data["exit_code"] == 1

    def test_to_langgraph_message_format(self) -> None:
        run = PytestRun(
            returncode=1,
            stdout=SAMPLE_STDOUT,
            stderr="",
            cmd=["pytest"],
        )
        result = build_result(repo_path="/repo", pytest_run=run)
        msg = result.to_langgraph_message()
        assert msg["role"] == "system"
        assert msg["name"] == "revisor"
        json.loads(msg["content"])  # deve ser JSON valido


# ---------------------------------------------------------------------------
# Agent (com runner mockado)
# ---------------------------------------------------------------------------

class TestAgent:
    def test_run_requires_repo_path(self) -> None:
        agent = RevisorAgent(runner=lambda **kw: None)
        with pytest.raises(ValueError, match="repo_path"):
            agent.run({})

    def test_run_with_mocked_runner(self) -> None:
        def fake_runner(**kwargs):
            return PytestRun(
                returncode=1,
                stdout=SAMPLE_STDOUT,
                stderr="",
                cmd=["pytest"],
            )

        agent = RevisorAgent(runner=fake_runner)
        out = agent.run({"repo_path": "/repo"})
        assert "revisor_result" in out
        assert "messages" in out
        assert out["revisor_result"].status == "failed"
        assert out["revisor_result"].exit_code == 1

    def test_run_passes_pytest_args_to_runner(self) -> None:
        received = {}

        def fake_runner(**kwargs):
            received.update(kwargs)
            return PytestRun(
                returncode=0,
                stdout="1 passed in 0.01s\n",
                stderr="",
                cmd=["pytest"],
            )

        agent = RevisorAgent(runner=fake_runner)
        out = agent.run({"repo_path": "/repo", "pytest_args": ["-x", "--tb=short"]})
        assert received["pytest_args"] == ["-x", "--tb=short"]
        assert out["revisor_result"].status == "passed"

    def test_run_handles_pytest_not_found(self) -> None:
        from agente_revisor.pytest_runner import PytestNotFoundError

        def boom(**kwargs):
            raise PytestNotFoundError("nope")

        agent = RevisorAgent(runner=boom)
        out = agent.run({"repo_path": "/repo"})
        assert out["revisor_result"].status == "error"
        assert out["revisor_result"].error is not None
        assert out["revisor_result"].exit_code == -1

    def test_run_handles_timeout(self) -> None:
        def boom(**kwargs):
            raise TimeoutError("timeout")

        agent = RevisorAgent(runner=boom)
        out = agent.run({"repo_path": "/repo"})
        assert out["revisor_result"].status == "error"
        assert out["revisor_result"].error is not None

    def test_as_node_returns_callable(self) -> None:
        def fake_runner(**kwargs):
            return PytestRun(
                returncode=0,
                stdout="1 passed in 0.01s\n",
                stderr="",
                cmd=[],
            )

        node = RevisorAgent(runner=fake_runner).as_node()
        assert callable(node)
        out = node({"repo_path": "/repo"})
        assert out["revisor_result"].status == "passed"
        assert node.__name__ == "revisor_node"


# ---------------------------------------------------------------------------
# End-to-end (pytest real)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("SKIP_E2E") == "1",
    reason="SKIP_E2E=1 definido",
)
def test_end_to_end_real_pytest(fake_repo: Path) -> None:
    """Corre o pytest real num repositorio de teste e valida o JSON final."""
    agent = RevisorAgent()
    out = agent.run({"repo_path": str(fake_repo)})
    result = out["revisor_result"]

    assert result.status == "failed"
    assert result.summary.total == 3
    assert result.summary.passed == 2
    assert result.summary.failed == 1
    assert result.exit_code != 0
    assert len(result.failures) == 1

    f = result.failures[0]
    assert f.test_name == "test_subtract_fails"
    assert f.error_type == "AssertionError"
    assert f.line == 5
    assert f.reproduction_steps[0].startswith("cd ")
    assert "pytest" in f.reproduction_steps[1]
    assert str(fake_repo) in f.reproduction_steps[0]

    # Garante que e serializavel e compativel com LangGraph.
    payload = json.loads(result.model_dump_json())
    assert payload["agent"] == "revisor"
    assert payload["failures"][0]["file"] == "tests/test_calc.py"
    assert payload["exit_code"] == 1


@pytest.mark.skipif(
    os.environ.get("SKIP_E2E") == "1",
    reason="SKIP_E2E=1 definido",
)
def test_end_to_end_class_based_test(fake_repo_class: Path) -> None:
    """E2E com testes baseados em classes: o `file` nao deve incluir a classe."""
    agent = RevisorAgent()
    out = agent.run({"repo_path": str(fake_repo_class)})
    result = out["revisor_result"]

    assert result.status == "failed"
    assert len(result.failures) == 1
    f = result.failures[0]
    assert f.test_name == "test_ten_percent_fails"
    assert f.file == "tests/test_discount.py"  # sem "::TestDiscount"
    assert "::TestDiscount" not in f.file
    assert f.error_type == "AssertionError"
    assert f.line is not None and f.line > 0
    assert f.traceback  # nao vazio
    # Passos de reproducao usam o nodeid completo (com classe) — pytest aceita.
    assert "test_ten_percent_fails" in f.reproduction_steps[1]


# ---------------------------------------------------------------------------
# CLI (entry-point __main__)
# ---------------------------------------------------------------------------

class TestCLI:
    def test_cli_main_failed_repo(
        self, fake_repo: Path, capsys: pytest.CaptureFixture
    ) -> None:
        from agente_revisor.__main__ import main

        rc = main(["--repo", str(fake_repo), "--indent", "0"])
        captured = capsys.readouterr()
        assert rc == 1
        data = json.loads(captured.out)
        assert data["status"] == "failed"
        assert data["summary"]["failed"] == 1
        assert data["exit_code"] != 0

    def test_cli_main_missing_repo(self, capsys: pytest.CaptureFixture) -> None:
        from agente_revisor.__main__ import main

        # argparse sai com SystemExit(2) quando um argumento obrigatorio falta.
        with pytest.raises(SystemExit) as exc:
            main([])
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert "--repo" in captured.err

    def test_cli_main_passed_returncode(self, fake_repo: Path, capsys: pytest.CaptureFixture) -> None:
        """CLI devolve exit code 0 quando todos os testes passam."""
        # Cria um repo com apenas testes que passam.
        clean_repo = fake_repo
        (clean_repo / "tests" / "test_calc.py").write_text(
            textwrap.dedent(
                """\
                def test_add_passes():
                    assert 1 + 1 == 2
                """
            )
        )
        from agente_revisor.__main__ import main

        rc = main(["--repo", str(clean_repo)])
        assert rc == 0
