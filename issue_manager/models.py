"""Contratos de dados do Agente 2 (Gestor de Issues).

BugReport  -> o que o Agente 1 (Analisador, Guidyanne) envia.
IssueResult -> o que o Agente 2 devolve ao orquestrador / Agente 3 (Programador, Ruben).

Combinem estes modelos com a equipa ANTES de programar: são a "interface" entre agentes.
"""
from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Severity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class BugReport(BaseModel):
    """Problema detetado pelo Analisador."""

    title: str = Field(min_length=10, max_length=120)
    description: str = Field(min_length=20)
    files: list[str] = Field(min_length=1, description="Ficheiros envolvidos, ex.: src/cart.py")
    reproduction_steps: list[str] = Field(min_length=1)
    expected_behavior: str
    actual_behavior: str
    evidence: str = Field(
        min_length=1,
        description="Prova objetiva: output do pytest a falhar, stack trace, etc.",
    )
    failing_test: Optional[str] = Field(
        default=None, description="ex.: tests/test_cart.py::test_desconto_10"
    )
    severity: Severity = Severity.medium
    reproduced: bool = Field(description="O Analisador conseguiu reproduzir o erro?")

    @field_validator("files")
    @classmethod
    def no_absolute_paths(cls, v: list[str]) -> list[str]:
        for f in v:
            if f.startswith("/") or ".." in f:
                raise ValueError(f"Caminho inválido (tem de ser relativo ao repo): {f}")
        return v

    def fingerprint(self) -> str:
        """Identificador estável do bug, usado para detetar duplicados.

        Baseia-se no teste que falha (ou nos ficheiros) + título normalizado,
        para que o mesmo bug detetado duas vezes gere o mesmo fingerprint.
        """
        anchor = self.failing_test or ",".join(sorted(self.files))
        norm_title = re.sub(r"[^a-z0-9 ]", "", self.title.lower())
        norm_title = re.sub(r"\s+", " ", norm_title).strip()
        raw = f"{anchor}|{norm_title}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


class IssueResult(BaseModel):
    """Resultado do Agente 2, guardado no estado do orquestrador."""

    status: Literal["created", "duplicate", "rejected"]
    reason: str
    issue_number: Optional[int] = None
    issue_url: Optional[str] = None
    branch_name: Optional[str] = None  # nome que o Agente 3 deve usar
    fingerprint: Optional[str] = None
