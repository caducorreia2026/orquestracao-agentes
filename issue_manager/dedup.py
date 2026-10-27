"""Deteção de issues duplicadas, em 3 camadas (da mais barata/fiável para a menos):

1. Fingerprint exato  -> escrito num comentário HTML escondido no corpo da issue.
2. Semelhança de texto -> difflib sobre título + ficheiros (sem IA, determinístico).
3. LLM (opcional)      -> só para a "zona cinzenta", ex.: um modelo local no Ollama.

A IA nunca decide sozinha nos casos claros: isto torna o agente previsível e testável.
"""
from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
from typing import Callable, Optional

import requests

from .models import BugReport

FP_MARKER = "<!-- bug-fingerprint: {fp} -->"
FP_REGEX = re.compile(r"<!-- bug-fingerprint: ([0-9a-f]{16}) -->")

DUPLICATE_THRESHOLD = 0.85  # acima disto: duplicado
GREY_ZONE_THRESHOLD = 0.45  # entre 0.45 e 0.85: pergunta ao LLM (se houver)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9à-ú ]", " ", s.lower())).strip()


def similarity(report: BugReport, issue: dict) -> float:
    """0..1 — compara títulos e verifica se a issue menciona os mesmos ficheiros."""
    issue_title = re.sub(r"^\[bug\]\s*", "", issue.get("title", ""), flags=re.I)
    title_score = SequenceMatcher(None, _norm(report.title), _norm(issue_title)).ratio()
    body = issue.get("body") or ""
    files_hit = sum(1 for f in report.files if f in body) / len(report.files)
    return 0.7 * title_score + 0.3 * files_hit


# Assinatura: (report, issue) -> True se for o mesmo bug
LLMJudge = Callable[[BugReport, dict], bool]


def ollama_judge(model: Optional[str] = None, host: Optional[str] = None) -> LLMJudge:
    """Juiz de duplicados com um modelo local via Ollama (os mesmos testados no Hermes)."""
    model = model or os.environ.get("OLLAMA_MODEL", "qwen3:8b")
    host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def judge(report: BugReport, issue: dict) -> bool:
        prompt = (
            "Decide se estes dois relatórios descrevem o MESMO bug de software.\n"
            'Responde só em JSON: {"same_bug": true|false, "reason": "..."}\n\n'
            f"NOVO:\nTítulo: {report.title}\nFicheiros: {report.files}\n"
            f"Esperado: {report.expected_behavior}\nObtido: {report.actual_behavior}\n\n"
            f"EXISTENTE (#{issue['number']}):\nTítulo: {issue['title']}\n"
            f"Corpo: {(issue.get('body') or '')[:1500]}"
        )
        r = requests.post(
            f"{host}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=120,
        )
        r.raise_for_status()
        try:
            return bool(json.loads(r.json()["message"]["content"]).get("same_bug"))
        except (json.JSONDecodeError, KeyError):
            return False  # na dúvida, não bloqueia a criação

    return judge


def find_duplicate(
    report: BugReport, existing: list[dict], llm_judge: Optional[LLMJudge] = None
) -> tuple[Optional[dict], str]:
    """Devolve (issue_duplicada | None, explicação)."""
    fp = report.fingerprint()

    # 1) fingerprint exato
    for issue in existing:
        m = FP_REGEX.search(issue.get("body") or "")
        if m and m.group(1) == fp:
            return issue, f"fingerprint igual ({fp})"

    # 2) semelhança textual
    scored = sorted(((similarity(report, i), i) for i in existing), key=lambda t: t[0], reverse=True)
    if not scored:
        return None, "sem issues existentes"
    best_score, best = scored[0]
    if best_score >= DUPLICATE_THRESHOLD:
        return best, f"semelhança {best_score:.2f} com #{best['number']}"

    # 3) zona cinzenta -> LLM
    if llm_judge and best_score >= GREY_ZONE_THRESHOLD:
        if llm_judge(report, best):
            return best, f"LLM confirmou duplicado de #{best['number']} (semelhança {best_score:.2f})"
        return None, f"LLM disse que #{best['number']} é outro bug (semelhança {best_score:.2f})"

    return None, f"melhor semelhança {best_score:.2f} < {DUPLICATE_THRESHOLD}"
