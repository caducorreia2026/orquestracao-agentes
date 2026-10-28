"""Esquemas Pydantic da saída estruturada do Agente Programador.

O formato é compatível com o estado partilhado entre agentes no Hermes/LangGraph:
qualquer nó pode ler `state["programador_result"]` e obter um `ProgramadorResult`
validado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ProgramadorResult(BaseModel):
    """Payload principal produzido pelo Agente Programador.

    Devolve o estado da correção: qual branch foi criada, o ficheiro alterado,
    se a substituição resultou numa mudança real e a mensagem de commit.
    """

    agent: Literal["programador"] = "programador"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
        description="Timestamp UTC ISO-8601 da execução.",
    )
    repo_path: str = Field(description="Caminho absoluto do repositório.")
    issue_id: str = Field(description="ID da issue que originou a correção.")
    branch: str = Field(description="Nome da branch onde a correção foi aplicada.")
    file_path: str = Field(description="Caminho do ficheiro corrigido (relativo ao repo).")
    changed: bool = Field(description="True se o conteúdo do ficheiro sofreu alteração.")
    commit: str | None = Field(
        default=None,
        description="Hash do commit criado, quando aplicável.",
    )
    commit_message: str = Field(description="Mensagem de commit utilizada.")
    error: str | None = Field(
        default=None,
        description="Erro fatal (ex.: branch já existe e não foi possível criar), quando aplicável.",
    )

    def to_langgraph_message(self) -> dict:
        """Converte o resultado numa mensagem compatível com Hermes/LangGraph."""
        return {
            "role": "system",
            "name": "programador",
            "content": self.model_dump_json(indent=2),
        }
