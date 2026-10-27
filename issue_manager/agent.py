"""Agente 2 — Gestor de Issues.

Responsabilidades (do enunciado):
  - validar se o problema está "devidamente fundamentado"
  - procurar issues existentes para evitar duplicados
  - criar a issue (descrição, ficheiros, passos, esperado, prioridade)
  - associar issue <-> branch <-> Pull Request
  - registar tudo o que fez e porquê (audit log)
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .dedup import FP_MARKER, LLMJudge, find_duplicate
from .models import BugReport, IssueResult, Severity

AUTO_LABEL = "auto-bug"
PRIORITY_LABELS = {
    Severity.critical: ("priority: P0", "b60205"),
    Severity.high: ("priority: P1", "d93f0b"),
    Severity.medium: ("priority: P2", "fbca04"),
    Severity.low: ("priority: P3", "0e8a16"),
}


class IssueManagerAgent:
    def __init__(self, github, audit_log: str | Path = "logs/issue_manager.jsonl",
                 llm_judge: Optional[LLMJudge] = None):
        self.gh = github
        self.llm_judge = llm_judge
        self.audit_path = Path(audit_log)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ log
    def _log(self, action: str, **data) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "agent": "issue_manager",
                 "action": action, **data}
        with self.audit_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------ validação
    @staticmethod
    def validate(report: BugReport) -> Optional[str]:
        """Devolve o motivo de rejeição, ou None se estiver fundamentado."""
        if not report.reproduced:
            return "o Analisador não conseguiu reproduzir o erro"
        if len(report.evidence.strip()) < 20:
            return "falta evidência objetiva (output de teste / stack trace)"
        if report.expected_behavior.strip() == report.actual_behavior.strip():
            return "comportamento esperado e obtido são iguais"
        return None

    # ------------------------------------------------------------- formatos
    @staticmethod
    def branch_name(issue_number: int, title: str) -> str:
        """Convenção partilhada com o Agente 3: fix/issue-<n>-<slug>."""
        ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:40].rstrip("-")
        return f"fix/issue-{issue_number}-{slug}"

    @staticmethod
    def render_body(report: BugReport) -> str:
        steps = "\n".join(f"{i}. {s}" for i, s in enumerate(report.reproduction_steps, 1))
        files = "\n".join(f"- `{f}`" for f in report.files)
        failing = f"\n**Teste que falha:** `{report.failing_test}`\n" if report.failing_test else ""
        return f"""## Descrição
{report.description}

## Ficheiros envolvidos
{files}

## Passos para reproduzir
{steps}

## Comportamento esperado
{report.expected_behavior}

## Comportamento obtido
{report.actual_behavior}
{failing}
## Evidência
<details><summary>Output</summary>

```
{report.evidence[:6000]}
```
</details>

---
_Issue criada automaticamente pelo Agente Gestor de Issues. Prioridade: **{report.severity.value}**._
{FP_MARKER.format(fp=report.fingerprint())}
"""

    # ------------------------------------------------------------ principal
    def process(self, report: BugReport) -> IssueResult:
        fp = report.fingerprint()
        self._log("received", title=report.title, fingerprint=fp)

        reason = self.validate(report)
        if reason:
            self._log("rejected", fingerprint=fp, reason=reason)
            return IssueResult(status="rejected", reason=reason, fingerprint=fp)

        existing = self.gh.list_issues(labels=AUTO_LABEL, state="all")
        dup, why = find_duplicate(report, existing, self.llm_judge)
        if dup:
            self.gh.comment_issue(
                dup["number"],
                f"O Analisador voltou a detetar este problema "
                f"({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC). Motivo do match: {why}.",
            )
            self._log("duplicate", fingerprint=fp, issue=dup["number"], reason=why)
            return IssueResult(
                status="duplicate", reason=why, fingerprint=fp,
                issue_number=dup["number"], issue_url=dup.get("html_url"),
                branch_name=self.branch_name(dup["number"], dup["title"]),
            )

        prio_label, color = PRIORITY_LABELS[report.severity]
        self.gh.ensure_label(AUTO_LABEL, "5319e7", "Criada pela orquestração de agentes")
        self.gh.ensure_label(prio_label, color)
        issue = self.gh.create_issue(
            title=f"[Bug] {report.title}",
            body=self.render_body(report),
            labels=[AUTO_LABEL, "bug", prio_label],
        )
        branch = self.branch_name(issue["number"], report.title)
        self._log("created", fingerprint=fp, issue=issue["number"], url=issue.get("html_url"),
                  branch=branch, dedup_check=why)
        return IssueResult(
            status="created", reason=why, fingerprint=fp,
            issue_number=issue["number"], issue_url=issue.get("html_url"), branch_name=branch,
        )

    # ------------------------------------------- ligação issue <-> branch <-> PR
    def link_pull_request(self, issue_number: int, pr_number: int, test_summary: str = "") -> None:
        """Chamado pelo orquestrador depois de o PR ser criado (Agente 3/4).

        - Garante "Closes #N" no corpo do PR -> o GitHub liga-os e fecha a issue
          só quando um humano fizer merge (aprovação humana obrigatória).
        - Comenta na issue com o link do PR e o resumo dos testes.
        """
        pr = self.gh.get_pull(pr_number)
        body = pr.get("body") or ""
        if not re.search(rf"\b(closes|fixes|resolves) #{issue_number}\b", body, re.I):
            self.gh.update_pull_body(pr_number, f"{body}\n\nCloses #{issue_number}".strip())
        msg = f"Correção proposta no PR #{pr_number} (branch `{pr['head']['ref']}`). Aguarda revisão humana."
        if test_summary:
            msg += f"\n\n**Testes:**\n```\n{test_summary[:3000]}\n```"
        self.gh.comment_issue(issue_number, msg)
        self._log("linked_pr", issue=issue_number, pr=pr_number, branch=pr["head"]["ref"])


# ---------------------------------------------------------------- LangGraph
def make_langgraph_node(agent: IssueManagerAgent):
    """Nó para o grafo do orquestrador (Eduardo).

    Lê state["bug_report"] (dict do Agente 1) e escreve state["issue"].
    O orquestrador decide o próximo passo com base em state["issue"]["status"]:
      created / duplicate -> Agente 3 (Programador) | rejected -> FIM ou volta ao Agente 1
    """
    def node(state: dict) -> dict:
        report = BugReport.model_validate(state["bug_report"])
        return {"issue": agent.process(report).model_dump()}

    return node
