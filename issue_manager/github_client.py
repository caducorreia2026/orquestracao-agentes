"""Cliente mínimo da API REST do GitHub, só com o que o Agente 2 precisa.

Segurança (requisito 6 do enunciado):
- Só aceita repositórios numa allowlist (ALLOWED_REPOS).
- Usa um fine-grained token limitado ao repositório de teste, com permissões:
    Issues: Read & write | Pull requests: Read & write | Metadata: Read
  (o Agente 2 NÃO precisa de Contents: write — isso é do Agente 3.)
"""
from __future__ import annotations

import os
from typing import Any, Optional

import requests

API = "https://api.github.com"


class RepoNotAllowed(Exception):
    pass


class GitHubClient:
    def __init__(self, repo: str, token: Optional[str] = None, allowed_repos: Optional[set[str]] = None):
        allowed = allowed_repos or {
            r.strip() for r in os.environ.get("ALLOWED_REPOS", "").split(",") if r.strip()
        }
        if repo not in allowed:
            raise RepoNotAllowed(f"Repositório '{repo}' não está em ALLOWED_REPOS={sorted(allowed)}")
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token or os.environ['GITHUB_TOKEN']}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    # ---------- helpers ----------
    def _req(self, method: str, path: str, **kw) -> Any:
        r = self.session.request(method, f"{API}{path}", timeout=20, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"GitHub {method} {path} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else None

    # ---------- issues ----------
    def list_issues(self, labels: str = "", state: str = "all", per_page: int = 100) -> list[dict]:
        """Lista issues (exclui PRs, que a API também devolve neste endpoint)."""
        items = self._req(
            "GET",
            f"/repos/{self.repo}/issues",
            params={"state": state, "labels": labels, "per_page": per_page},
        )
        return [i for i in items if "pull_request" not in i]

    def search_issues(self, text: str) -> list[dict]:
        q = f'repo:{self.repo} is:issue "{text}" in:body'
        return self._req("GET", "/search/issues", params={"q": q})["items"]

    def create_issue(self, title: str, body: str, labels: list[str]) -> dict:
        return self._req(
            "POST", f"/repos/{self.repo}/issues", json={"title": title, "body": body, "labels": labels}
        )

    def comment_issue(self, number: int, body: str) -> dict:
        return self._req("POST", f"/repos/{self.repo}/issues/{number}/comments", json={"body": body})

    def ensure_label(self, name: str, color: str, description: str = "") -> None:
        try:
            self._req("GET", f"/repos/{self.repo}/labels/{name}")
        except RuntimeError:
            self._req(
                "POST",
                f"/repos/{self.repo}/labels",
                json={"name": name, "color": color, "description": description},
            )

    # ---------- pull requests ----------
    def get_pull(self, number: int) -> dict:
        return self._req("GET", f"/repos/{self.repo}/pulls/{number}")

    def update_pull_body(self, number: int, body: str) -> dict:
        return self._req("PATCH", f"/repos/{self.repo}/pulls/{number}", json={"body": body})
