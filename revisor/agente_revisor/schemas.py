"""Esquemas Pydantic da saída estruturada do Agente Revisor.

O formato e compatível com o estado partilhado entre agentes no Hermes/LangGraph:
qualquer nó pode ler ``state["revisor_result"]`` e obter um ``RevisorResult``
validado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class Failure(BaseModel):
    """Um unico teste falhado, com informacao de localizacao e reproducao."""

    test_id: str = Field(
        description="Identificador completo do teste no formato 'ficheiro::nome'.",
    )
    file: str = Field(description="Caminho do ficheiro de teste afetado.")
    test_name: str = Field(description="Nome do teste (funcao/metodo).")
    line: int | None = Field(
        default=None, description="Linha onde ocorreu a falha, se disponivel.",
    )
    error_type: str = Field(description="Tipo/excecao do erro (ex.: AssertionError).")
    error_message: str = Field(description="Mensagem curta do erro.")
    traceback: str = Field(default="", description="Traceback completo capturado.")
    reproduction_steps: list[str] = Field(
        default_factory=list,
        description="Passos exatos para reproduzir o erro isoladamente.",
    )

    model_config = {"json_schema_extra": {"example": {
        "test_id": "tests/test_foo.py::test_bar",
        "file": "tests/test_foo.py",
        "test_name": "test_bar",
        "line": 42,
        "error_type": "AssertionError",
        "error_message": "assert 1 == 2",
        "traceback": "...",
        "reproduction_steps": [
            "cd /path/to/repo",
            "pytest tests/test_foo.py::test_bar -v",
        ],
    }}}


class Summary(BaseModel):
    """Resumo agregado da execucao do pytest."""

    total: int = Field(default=0, ge=0)
    passed: int = Field(default=0, ge=0)
    failed: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    skipped: int = Field(default=0, ge=0)
    duration_seconds: float = Field(default=0.0, ge=0.0)


class RevisorResult(BaseModel):
    """Payload principal produzido pelo Agente Revisor.

    Devolve o resultado da execucao do pytest num formato estruturado, pronto
    para viajar dentro do estado do LangGraph (em ``state["revisor_result"]``).

    Contrato de estado:
        Entrada:
            state["repo_path"]  - caminho absoluto do repositorio onde correr pytest.
        Saida:
            state["revisor_result"] = RevisorResult (validado)
    """

    agent: Literal["revisor"] = "revisor"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
        description="Timestamp UTC ISO-8601 da execucao.",
    )
    repo_path: str = Field(description="Caminho absoluto do repositorio testado.")
    status: Literal["passed", "failed", "error", "no_tests"] = "failed"
    exit_code: int = Field(description="Codigo de saida do processo pytest.")
    summary: Summary = Field(default_factory=Summary)
    failures: list[Failure] = Field(default_factory=list)
    raw_output: str = Field(
        default="",
        description="Saida bruta do pytest (truncada) para auditoria.",
    )
    error: str | None = Field(
        default=None,
        description="Erro fatal (ex.: pytest nao encontrado), quando aplicavel.",
    )

    def to_langgraph_message(self) -> dict:
        """Converte o resultado numa mensagem compativel com Hermes/LangGraph."""
        return {
            "role": "system",
            "name": "revisor",
            "content": self.model_dump_json(indent=2),
        }


__all__ = ["RevisorResult", "Failure", "Summary"]
